"""Light platform for MeRGBW integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, DEVICE_TYPE_NAMES
from .protocol import MeRGBWDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MeRGBW light based on a config entry."""
    device: MeRGBWDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MeRGBWLight(device, entry)])


class MeRGBWLight(RestoreEntity, LightEntity):
    """Representation of a MeRGBW light.

    Note: The MeRGBW protocol does not support reading the current color from
    the device - only power state and brightness are returned by SYNC_STATUS.
    We use RestoreEntity to remember the last-known color across restarts.
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB
    _attr_should_poll = False

    def __init__(self, device: MeRGBWDevice, entry: ConfigEntry) -> None:
        """Initialize the light."""
        self._device = device
        self._entry = entry
        self._attr_unique_id = device.address
        # Device is considered available if we've seen it via BLE advertisements
        # (which we have if setup succeeded). It may not be connected though.
        self._ble_available = True
        self._connected = False

        self._device_type = entry.data.get("device_type", 2)
        model = entry.data.get("model", "")
        self._device_type_name = DEVICE_TYPE_NAMES.get(self._device_type, f"Type {self._device_type}")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.address)},
            name=device.name,
            manufacturer="MeRGBW",
            model=model or "Unknown",
            hw_version=self._device_type_name,
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        # Restore previous state (color and brightness) since the device
        # protocol doesn't report current color
        if (last_state := await self.async_get_last_state()) is not None:
            _LOGGER.debug(
                "Restoring previous state for %s: %s",
                self._device.address,
                last_state.attributes,
            )

            # Restore brightness
            if (brightness := last_state.attributes.get(ATTR_BRIGHTNESS)) is not None:
                # Convert HA brightness (0-255) to device brightness (0-100)
                self._device.state.brightness = int(brightness * 100 / 255)

            # Restore RGB color
            if (rgb := last_state.attributes.get(ATTR_RGB_COLOR)) is not None:
                self._device.state.red = rgb[0]
                self._device.state.green = rgb[1]
                self._device.state.blue = rgb[2]

        self._device.register_disconnect_callback(self._handle_disconnect)
        self._device.register_available_callback(self._handle_available)

        # Connect and sync power state (the only state the device reports reliably)
        await self._ensure_connected()

    @callback
    def _handle_disconnect(self) -> None:
        """Handle device disconnect."""
        _LOGGER.debug("Device %s disconnected", self._device.address)
        self._connected = False
        self.async_write_ha_state()

    @callback
    def _handle_available(self) -> None:
        """Handle device becoming available (BLE advertisement received)."""
        _LOGGER.debug("Device %s is available via BLE", self._device.address)
        was_available = self._ble_available
        self._ble_available = True
        if not was_available:
            self.async_write_ha_state()

    async def _ensure_connected(self) -> bool:
        """Ensure device is connected."""
        if self._device.is_connected:
            return True

        if await self._device.connect():
            self._connected = True
            self._ble_available = True
            await self._device.sync_status()
            self.async_write_ha_state()
            return True

        _LOGGER.debug("Failed to connect to %s", self._device.address)
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available.

        The entity is available if we've recently seen the device via BLE
        advertisements. Being disconnected doesn't mean unavailable - BLE
        devices disconnect when not in use to save power.
        """
        return self._ble_available

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._device.state.power

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return int(self._device.state.brightness * 255 / 100)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value."""
        state = self._device.state
        return (state.red, state.green, state.blue)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "device_type": self._device_type,
            "device_type_name": self._device_type_name,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if not await self._ensure_connected():
            return

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        rgb = kwargs.get(ATTR_RGB_COLOR)
        
        # Convert HA brightness (0-255) to device brightness (0-100)
        device_brightness = int(brightness * 100 / 255) if brightness else None
        
        await self._device.turn_on(brightness=device_brightness, rgb=rgb)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if not await self._ensure_connected():
            return

        await self._device.turn_off()
        self.async_write_ha_state()