"""Light platform for MeRGBW integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
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


class MeRGBWLight(LightEntity):
    """Representation of a MeRGBW light."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB

    def __init__(self, device: MeRGBWDevice, entry: ConfigEntry) -> None:
        """Initialize the light."""
        self._device = device
        self._entry = entry
        self._attr_unique_id = device.address
        self._connected = False
        
        device_type = entry.data.get("device_type", 2)
        model = entry.data.get("model", "")
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.address)},
            name=device.name,
            manufacturer="MeRGBW",
            model=model or "Unknown",
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self._device.register_disconnect_callback(self._handle_disconnect)
        # Initial connection and sync
        await self._ensure_connected()

    @callback
    def _handle_disconnect(self) -> None:
        """Handle device disconnect."""
        self._connected = False
        self.async_write_ha_state()

    async def _ensure_connected(self) -> bool:
        """Ensure device is connected."""
        if self._device.is_connected:
            return True
        
        if await self._device.connect():
            self._connected = True
            await self._device.sync_status()
            self.async_write_ha_state()
            return True
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._connected or self._device.is_connected

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

    async def async_update(self) -> None:
        """Fetch new state data for this light."""
        if await self._ensure_connected():
            await self._device.sync_status()