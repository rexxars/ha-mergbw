"""Tests for MeRGBW protocol implementation."""
from __future__ import annotations

import pytest

from custom_components.mergbw.protocol import (
    build_packet,
    calculate_checksum,
    validate_response,
    rgb_to_hsv_payload,
    DeviceState,
)
from custom_components.mergbw.const import (
    HEADER_CMD,
    HEADER_RSP,
    CMD_POWER,
    CMD_SYNC_STATUS,
    CMD_SET_COLOR,
    CMD_SET_BRIGHTNESS,
)


class TestChecksum:
    """Tests for checksum calculation and validation."""

    def test_calculate_checksum_power_on(self):
        """Test checksum calculation for power on command."""
        # Power ON packet without checksum: [0x55, 0x01, 0xFF, 0x05, 0x01]
        # Expected checksum: 0xA4 (from protocol docs)
        packet = bytes([0x55, 0x01, 0xFF, 0x05, 0x01])
        assert calculate_checksum(packet) == 0xA4

    def test_calculate_checksum_power_off(self):
        """Test checksum calculation for power off command."""
        # Power OFF packet without checksum: [0x55, 0x01, 0xFF, 0x05, 0x00]
        # Expected checksum: 0xA5 (from protocol docs)
        packet = bytes([0x55, 0x01, 0xFF, 0x05, 0x00])
        assert calculate_checksum(packet) == 0xA5

    def test_validate_response_valid(self):
        """Test that valid responses pass validation."""
        # Valid response: sum of all bytes + (~sum) should equal 0xFF
        # Build a valid packet with correct checksum
        packet = bytes([0x56, 0x00, 0xFF, 0x05, 0x01])
        checksum = calculate_checksum(packet)
        full_packet = packet + bytes([checksum])
        assert validate_response(full_packet) is True

    def test_validate_response_invalid_checksum(self):
        """Test that invalid checksums fail validation."""
        # Packet with wrong checksum
        packet = bytes([0x56, 0x00, 0xFF, 0x05, 0x01, 0x00])  # Wrong checksum
        assert validate_response(packet) is False

    def test_validate_response_too_short(self):
        """Test that packets shorter than 4 bytes fail validation."""
        assert validate_response(bytes([0x56, 0x00, 0xFF])) is False
        assert validate_response(bytes([0x56, 0x00])) is False
        assert validate_response(bytes([0x56])) is False
        assert validate_response(bytes([])) is False

    def test_validate_response_wrong_header(self):
        """Test that packets with wrong header fail validation."""
        # Build a packet with invalid header but valid checksum
        packet = bytes([0x00, 0x00, 0xFF, 0x05, 0x01])
        checksum = calculate_checksum(packet)
        full_packet = packet + bytes([checksum])
        assert validate_response(full_packet) is False

    def test_validate_response_accepts_both_headers(self):
        """Test that both 0x55 and 0x56 headers are accepted."""
        # Command header (0x55)
        packet_cmd = bytes([0x55, 0x00, 0xFF, 0x05, 0x01])
        checksum_cmd = calculate_checksum(packet_cmd)
        assert validate_response(packet_cmd + bytes([checksum_cmd])) is True

        # Response header (0x56)
        packet_rsp = bytes([0x56, 0x00, 0xFF, 0x05, 0x01])
        checksum_rsp = calculate_checksum(packet_rsp)
        assert validate_response(packet_rsp + bytes([checksum_rsp])) is True


class TestBuildPacket:
    """Tests for packet building."""

    def test_build_packet_no_payload(self):
        """Test building a packet with no payload (e.g., SYNC_STATUS)."""
        packet = build_packet(CMD_SYNC_STATUS)
        # Format: [header, cmd, seq, length, checksum]
        # Length = 5 (header + cmd + seq + length + checksum)
        assert packet[0] == HEADER_CMD  # 0x55
        assert packet[1] == CMD_SYNC_STATUS  # 0x00
        assert packet[2] == 0xFF  # Single packet sequence
        assert packet[3] == 5  # Length
        # Verify checksum is correct
        assert validate_response(packet) is True

    def test_build_packet_with_payload(self):
        """Test building a packet with payload (e.g., POWER ON)."""
        packet = build_packet(CMD_POWER, bytes([0x01]))
        # Format: [header, cmd, seq, length, payload, checksum]
        # Length = 6 (header + cmd + seq + length + 1 payload + checksum)
        assert packet[0] == HEADER_CMD
        assert packet[1] == CMD_POWER
        assert packet[2] == 0xFF
        assert packet[3] == 6  # Length includes payload
        assert packet[4] == 0x01  # Payload
        assert validate_response(packet) is True

    def test_build_packet_rgb_color(self):
        """Test building a packet with RGB color payload."""
        # Set color to red (255, 0, 0)
        packet = build_packet(CMD_SET_COLOR, bytes([0xFF, 0x00, 0x00]))
        assert packet[0] == HEADER_CMD
        assert packet[1] == CMD_SET_COLOR
        assert packet[2] == 0xFF
        assert packet[3] == 8  # 5 + 3 payload bytes
        assert packet[4:7] == bytes([0xFF, 0x00, 0x00])
        assert validate_response(packet) is True

    def test_build_packet_brightness_two_byte(self):
        """Test building brightness packet for types 1/2/4 (2-byte format)."""
        # 50% brightness: (50 + 5) * 10 = 550 = 0x0226
        value = (50 + 5) * 10
        payload = bytes([(value >> 8) & 0xFF, value & 0xFF])
        packet = build_packet(CMD_SET_BRIGHTNESS, payload)
        assert packet[4] == 0x02
        assert packet[5] == 0x26
        assert validate_response(packet) is True

    def test_build_packet_brightness_one_byte(self):
        """Test building brightness packet for types 6/7/8 (1-byte format)."""
        # 50% brightness: 50 + 5 = 55 = 0x37
        payload = bytes([50 + 5])
        packet = build_packet(CMD_SET_BRIGHTNESS, payload)
        assert packet[4] == 0x37
        assert validate_response(packet) is True


class TestRGBToHSV:
    """Tests for RGB to HSV conversion."""

    def test_rgb_to_hsv_red(self):
        """Test converting pure red to HSV."""
        payload = rgb_to_hsv_payload(255, 0, 0)
        # Red: Hue = 0, Saturation = 1000 (100%)
        hue = (payload[0] << 8) | payload[1]
        sat = (payload[2] << 8) | payload[3]
        assert hue == 0
        assert sat == 1000

    def test_rgb_to_hsv_green(self):
        """Test converting pure green to HSV."""
        payload = rgb_to_hsv_payload(0, 255, 0)
        # Green: Hue = 120, Saturation = 1000 (100%)
        hue = (payload[0] << 8) | payload[1]
        sat = (payload[2] << 8) | payload[3]
        assert hue == 120
        assert sat == 1000

    def test_rgb_to_hsv_blue(self):
        """Test converting pure blue to HSV."""
        payload = rgb_to_hsv_payload(0, 0, 255)
        # Blue: Hue = 240, Saturation = 1000 (100%)
        hue = (payload[0] << 8) | payload[1]
        sat = (payload[2] << 8) | payload[3]
        assert hue == 240
        assert sat == 1000

    def test_rgb_to_hsv_white(self):
        """Test converting white to HSV."""
        payload = rgb_to_hsv_payload(255, 255, 255)
        # White: Saturation = 0 (no color)
        sat = (payload[2] << 8) | payload[3]
        assert sat == 0

    def test_rgb_to_hsv_cyan(self):
        """Test converting cyan to HSV."""
        payload = rgb_to_hsv_payload(0, 255, 255)
        # Cyan: Hue = 180
        hue = (payload[0] << 8) | payload[1]
        sat = (payload[2] << 8) | payload[3]
        assert hue == 180
        assert sat == 1000

    def test_rgb_to_hsv_payload_length(self):
        """Test that HSV payload is always 4 bytes."""
        payload = rgb_to_hsv_payload(128, 64, 192)
        assert len(payload) == 4


class TestDeviceState:
    """Tests for DeviceState dataclass."""

    def test_device_state_defaults(self):
        """Test default values for DeviceState."""
        state = DeviceState()
        assert state.power is False
        assert state.brightness == 100
        assert state.red == 255
        assert state.green == 255
        assert state.blue == 255
        assert state.device_type == 2
        assert state.led_count == 0
        assert state.firmware == ""

    def test_device_state_with_values(self):
        """Test DeviceState with custom values."""
        state = DeviceState(
            power=True,
            brightness=50,
            red=255,
            green=0,
            blue=128,
            device_type=6,
            led_count=300,
            firmware="V04",
        )
        assert state.power is True
        assert state.brightness == 50
        assert state.red == 255
        assert state.green == 0
        assert state.blue == 128
        assert state.device_type == 6
        assert state.led_count == 300
        assert state.firmware == "V04"

    def test_device_state_mutable(self):
        """Test that DeviceState attributes can be modified."""
        state = DeviceState()
        state.power = True
        state.brightness = 75
        state.red = 100
        assert state.power is True
        assert state.brightness == 75
        assert state.red == 100


class TestProtocolExamples:
    """Tests based on protocol documentation.

    Note: The length field in our implementation includes ALL bytes in the packet
    (header + cmd + seq + length + payload + checksum), which matches the protocol
    spec definition: "Total packet length including header and checksum"
    """

    def test_sync_status_command(self):
        """Test SYNC_STATUS command structure."""
        packet = build_packet(CMD_SYNC_STATUS)
        # Length = 5: header(1) + cmd(1) + seq(1) + length(1) + checksum(1)
        assert packet[0] == 0x55  # Header
        assert packet[1] == CMD_SYNC_STATUS  # Command
        assert packet[2] == 0xFF  # Single packet sequence
        assert packet[3] == 5  # Length (total packet size)
        assert len(packet) == 5
        assert validate_response(packet)  # Checksum is valid

    def test_power_on_command(self):
        """Test power ON command structure."""
        packet = build_packet(CMD_POWER, bytes([0x01]))
        # Length = 6: header(1) + cmd(1) + seq(1) + length(1) + payload(1) + checksum(1)
        assert packet[0] == 0x55
        assert packet[1] == CMD_POWER
        assert packet[2] == 0xFF
        assert packet[3] == 6  # Length
        assert packet[4] == 0x01  # Payload: ON
        assert len(packet) == 6
        assert validate_response(packet)

    def test_power_off_command(self):
        """Test power OFF command structure."""
        packet = build_packet(CMD_POWER, bytes([0x00]))
        assert packet[0] == 0x55
        assert packet[1] == CMD_POWER
        assert packet[2] == 0xFF
        assert packet[3] == 6  # Length
        assert packet[4] == 0x00  # Payload: OFF
        assert len(packet) == 6
        assert validate_response(packet)

    def test_set_red_color_command(self):
        """Test setting red color command structure."""
        packet = build_packet(CMD_SET_COLOR, bytes([0xFF, 0x00, 0x00]))
        # Length = 8: header(1) + cmd(1) + seq(1) + length(1) + payload(3) + checksum(1)
        assert packet[0] == 0x55
        assert packet[1] == CMD_SET_COLOR
        assert packet[2] == 0xFF
        assert packet[3] == 8  # Length
        assert packet[4:7] == bytes([0xFF, 0x00, 0x00])  # RGB payload
        assert len(packet) == 8
        assert validate_response(packet)

    def test_set_green_color_command(self):
        """Test setting green color command structure."""
        packet = build_packet(CMD_SET_COLOR, bytes([0x00, 0xFF, 0x00]))
        assert packet[0] == 0x55
        assert packet[1] == CMD_SET_COLOR
        assert packet[3] == 8
        assert packet[4:7] == bytes([0x00, 0xFF, 0x00])
        assert validate_response(packet)

    def test_set_blue_color_command(self):
        """Test setting blue color command structure."""
        packet = build_packet(CMD_SET_COLOR, bytes([0x00, 0x00, 0xFF]))
        assert packet[0] == 0x55
        assert packet[1] == CMD_SET_COLOR
        assert packet[3] == 8
        assert packet[4:7] == bytes([0x00, 0x00, 0xFF])
        assert validate_response(packet)
