
"""MeRGBW Bluetooth protocol implementation."""
from __future__ import annotations

import asyncio
import colorsys
import logging
from dataclasses import dataclass
from typing import Callable

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from .const import (
    WRITE_CHAR_UUID,
    NOTIFY_CHAR_UUID,
    HEADER_CMD,
    HEADER_RSP,
    SEQ_SINGLE,
    CMD_SYNC_STATUS,
    CMD_POWER,
    CMD_SET_COLOR,
    CMD_SET_BRIGHTNESS,
    CMD_CHECK_BIND_STATE,
    TWO_BYTE_BRIGHTNESS_TYPES,
    BINDING_REQUIRED_TYPES,
    BIND_STATE_BOUND,
)

_LOGGER = logging.getLogger(__name__)


# Device types that use HSV color format (addressable LED devices)
HSV_COLOR_TYPES = {1, 2, 4}  # Letters, RGB Line, Handle


def calculate_checksum(data: bytes) -> int:
    """Calculate checksum for packet."""
    return (~sum(data)) & 0xFF


def build_packet(command: int, payload: bytes = b"") -> bytes:
    """Build a command packet.

    Length field = header + cmd + seq + length + payload + checksum (INCLUDES checksum)
    """
    length = 5 + len(payload)  # header(1) + cmd(1) + seq(1) + length(1) + payload(N) + checksum(1)
    packet = bytes([HEADER_CMD, command, SEQ_SINGLE, length]) + payload
    return packet + bytes([calculate_checksum(packet)])


def validate_response(data: bytes) -> bool:
    """Validate response checksum."""
    if len(data) < 4:
        return False
    # Accept both 0x55 and 0x56 headers - protocol docs are inconsistent
    if data[0] not in (HEADER_CMD, HEADER_RSP):
        return False
    checksum_valid = ((~sum(data)) & 0xFF) == 0
    if not checksum_valid:
        _LOGGER.debug("Checksum validation failed for: %s", data.hex())
    return checksum_valid


def rgb_to_hsv_payload(r: int, g: int, b: int) -> bytes:
    """Convert RGB to HSV payload for device types 1, 2, 4.

    Returns 4 bytes: [H_high, H_low, S_high, S_low]
    Hue: 0-360 degrees as 2 bytes big-endian
    Saturation: 0-1000 (0.0-1.0 scaled by 1000) as 2 bytes big-endian
    """
    # Convert RGB (0-255) to HSV
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

    # Convert to protocol format
    hue = int(h * 360)  # 0-360
    sat = int(s * 1000)  # 0-1000

    return bytes([
        (hue >> 8) & 0xFF, hue & 0xFF,
        (sat >> 8) & 0xFF, sat & 0xFF,
    ])


@dataclass
class DeviceState:
    """Current state of a MeRGBW device."""
    power: bool = False
    brightness: int = 100
    red: int = 255
    green: int = 255
    blue: int = 255
    device_type: int = 2
    led_count: int = 0
    firmware: str = ""


class MeRGBWDevice:
    """Represents a MeRGBW Bluetooth device."""

    def __init__(self, ble_device: BLEDevice, device_type: int = 2) -> None:
        self._ble_device = ble_device
        self._client: BleakClient | None = None
        self._state = DeviceState(device_type=device_type)
        self._response_event = asyncio.Event()
        self._last_response: bytes = b""
        self._lock = asyncio.Lock()
        self._disconnect_callbacks: list[Callable[[], None]] = []
        self._available_callbacks: list[Callable[[], None]] = []

    @property
    def address(self) -> str:
        return self._ble_device.address

    @property
    def name(self) -> str:
        name = self._ble_device.name or "MeRGBW Light"
        # Strip null bytes and whitespace that may be in advertised name
        return name.strip('\x00 ')

    @property
    def state(self) -> DeviceState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    def register_disconnect_callback(self, callback: Callable[[], None]) -> None:
        self._disconnect_callbacks.append(callback)

    def register_available_callback(self, callback: Callable[[], None]) -> None:
        """Register callback for when device becomes available again."""
        self._available_callbacks.append(callback)

    def update_ble_device(self, ble_device: BLEDevice) -> None:
        """Update the BLE device reference when HA discovers an update.

        This is called when the device is rediscovered after going out of range,
        providing a fresh BLEDevice object for reconnection.
        """
        self._ble_device = ble_device
        _LOGGER.debug("Updated BLE device reference for %s", self.address)
        # Notify listeners that device is available for connection
        for callback in self._available_callbacks:
            callback()

    def _handle_disconnect(self, client: BleakClient) -> None:
        _LOGGER.debug("Device %s disconnected", self.address)
        for callback in self._disconnect_callbacks:
            callback()

    def _handle_notification(self, sender: int, data: bytes) -> None:
        _LOGGER.debug("Received notification from %s: %s (len=%d)", sender, data.hex(), len(data))
        if len(data) >= 2:
            _LOGGER.debug("  Header: 0x%02x, Command: 0x%02x", data[0], data[1])
        if validate_response(data):
            self._last_response = data
            self._response_event.set()
        else:
            _LOGGER.warning("Invalid response: %s", data.hex())

    async def connect(self) -> bool:
        """Connect to the device."""
        try:
            self._client = await establish_connection(
                BleakClient,
                self._ble_device,
                self.name,
                disconnected_callback=self._handle_disconnect,
            )

            # Log available services and characteristics for debugging
            for service in self._client.services:
                _LOGGER.debug("Service: %s", service.uuid)
                for char in service.characteristics:
                    _LOGGER.debug("  Char: %s, props: %s", char.uuid, char.properties)

            # Enable notifications
            _LOGGER.debug("Enabling notifications on %s", NOTIFY_CHAR_UUID)
            await self._client.start_notify(NOTIFY_CHAR_UUID, self._handle_notification)
            # Wait for notifications to be ready before sending commands (JS ref uses 500ms)
            await asyncio.sleep(0.5)
            _LOGGER.info("Connected to %s (device_type=%d)", self.name, self._state.device_type)
            return True
        except Exception as e:
            _LOGGER.error("Failed to connect to %s: %s", self.name, e)
            return False

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._client:
            try:
                await self._client.disconnect()
            except Exception as e:
                _LOGGER.debug("Error during disconnect: %s", e)
            self._client = None

    async def _send_command(self, command: int, payload: bytes = b"", wait_response: bool = True) -> bytes | None:
        """Send a command and optionally wait for response."""
        if not self._client or not self._client.is_connected:
            _LOGGER.error("Not connected to device")
            return None

        async with self._lock:
            packet = build_packet(command, payload)
            _LOGGER.debug("Sending command 0x%02x to %s: %s", command, WRITE_CHAR_UUID, packet.hex())

            self._response_event.clear()
            try:
                # Use write without response - some devices don't support write-with-response
                await self._client.write_gatt_char(WRITE_CHAR_UUID, packet, response=False)
                _LOGGER.debug("Write completed for command 0x%02x", command)
            except Exception as e:
                _LOGGER.error("Failed to write command 0x%02x: %s", command, e)
                return None

            if wait_response:
                try:
                    await asyncio.wait_for(self._response_event.wait(), timeout=2.0)
                    return self._last_response
                except asyncio.TimeoutError:
                    _LOGGER.warning("Timeout waiting for response to command 0x%02x", command)
                    return None

            # Small delay between commands per protocol spec
            await asyncio.sleep(0.1)
            return b""

    async def check_bind_state(self, unique_id: bytes) -> int | None:
        """Check device binding state (for types 1 and 4)."""
        if self._state.device_type not in BINDING_REQUIRED_TYPES:
            return BIND_STATE_BOUND

        response = await self._send_command(CMD_CHECK_BIND_STATE, unique_id)
        if response and len(response) >= 5:
            return response[4]
        return None

    async def sync_status(self) -> bool:
        """Sync device status.

        Response format for types 1/2/4 (addressable devices):
        - Byte 4: Power state (0x01=ON, 0x00=OFF)
        - Bytes 5-6: Brightness (big-endian)
        - Bytes 7-10: Open alarm data
        - Bytes 11-14: Close alarm data
        - Bytes 15-16: LED count (big-endian)
        - Byte 17: Music sensitivity
        """
        response = await self._send_command(CMD_SYNC_STATUS)
        if not response or len(response) < 5:
            _LOGGER.warning("No response or too short response from SYNC_STATUS")
            return False

        # Log full response for debugging
        _LOGGER.debug("SYNC_STATUS response (%d bytes): %s", len(response), response.hex())

        # Parse response - byte 4 is power state (payload byte 0)
        self._state.power = response[4] == 0x01

        # Parse brightness - format varies by device type
        if self._state.device_type in TWO_BYTE_BRIGHTNESS_TYPES:
            # Types 1, 2, 4: 2-byte brightness at bytes 5-6 (big-endian)
            # Type 2: value / 10
            # Types 1 and 4: (value / 10) - 5
            if len(response) >= 7:
                brightness_raw = (response[5] << 8) | response[6]

                if self._state.device_type == 2:
                    self._state.brightness = brightness_raw // 10
                else:
                    self._state.brightness = (brightness_raw // 10) - 5
        else:
            # Types 3, 5, 6, 7, 8: Likely 1-byte brightness at byte 5
            # Formula: value - 5 (mirrors the command format)
            if len(response) >= 6:
                brightness_raw = response[5]
                self._state.brightness = brightness_raw - 5

        self._state.brightness = max(0, min(100, self._state.brightness))

        # Parse LED count for addressable devices (bytes 15-16)
        if len(response) >= 17:
            led_count = (response[15] << 8) | response[16]
            self._state.led_count = led_count
            _LOGGER.info("Device reports LED/segment count: %d", led_count)

        _LOGGER.debug("Synced state: power=%s, brightness=%d, led_count=%d",
                     self._state.power, self._state.brightness, self._state.led_count)
        return True

    async def set_power(self, on: bool) -> bool:
        """Turn device on or off."""
        payload = bytes([0x01 if on else 0x00])
        result = await self._send_command(CMD_POWER, payload, wait_response=False)
        if result is not None:
            self._state.power = on
            return True
        return False

    async def set_color(self, red: int, green: int, blue: int) -> bool:
        """Set RGB color.

        Device types 1, 2, 4 (addressable LEDs) use HSV format.
        Device types 6, 7, 8 (bulbs/ceiling) use RGB format.

        We try RGB format first since it works for most devices,
        then fall back to HSV if device type suggests it.
        """
        r = max(0, min(255, red))
        g = max(0, min(255, green))
        b = max(0, min(255, blue))

        # Try RGB format first - works for types 6, 7, 8 and seems more common
        payload_rgb = bytes([r, g, b])
        _LOGGER.debug("Setting RGB color: RGB(%d,%d,%d) -> payload %s",
                     r, g, b, payload_rgb.hex())
        result = await self._send_command(CMD_SET_COLOR, payload_rgb, wait_response=False)

        # If device type suggests HSV, also send HSV format
        if self._state.device_type in HSV_COLOR_TYPES:
            payload_hsv = rgb_to_hsv_payload(r, g, b)
            _LOGGER.debug("Also sending HSV color for type %d: RGB(%d,%d,%d) -> payload %s",
                         self._state.device_type, r, g, b, payload_hsv.hex())
            await self._send_command(CMD_SET_COLOR, payload_hsv, wait_response=False)

        if result is not None:
            self._state.red = r
            self._state.green = g
            self._state.blue = b
            return True
        return False

    async def set_brightness(self, brightness: int) -> bool:
        """Set brightness (0-100)."""
        brightness = max(0, min(100, brightness))

        if self._state.device_type == 2:
            # Type 2: use only the 2-byte brightness command.
            # The tested RGB Line controller uses a range of 0-1000
            # without the +5 offset.
            # The original offset caused color distortion above 95%.
            value = brightness * 10
            payload = value.to_bytes(2, "big")

            result = await self._send_command(
                CMD_SET_BRIGHTNESS,
                payload,
                wait_response=False
            )
        else:
            # Preserve the original brightness behavior for other types.
            payload_1byte = bytes([brightness + 5])

            result = await self._send_command(
                CMD_SET_BRIGHTNESS,
                payload_1byte,
                wait_response=False
            )

            value = (brightness + 5) * 10
            payload_2byte = value.to_bytes(2, "big")

            await self._send_command(
                CMD_SET_BRIGHTNESS,
                payload_2byte,
                wait_response=False
            )

        if result is not None:
            self._state.brightness = brightness
            return True

        return False

    async def turn_on(self, brightness: int | None = None, rgb: tuple[int, int, int] | None = None) -> bool:
        """Turn on with optional brightness and color."""
        success = True

        # Always send power on command first for immediate visual feedback
        success = await self.set_power(True) and success

        if rgb:
            success = await self.set_color(*rgb) and success

        if brightness is not None:
            success = await self.set_brightness(brightness) and success

        return success

    async def turn_off(self) -> bool:
        """Turn off the device."""
        return await self.set_power(False)
