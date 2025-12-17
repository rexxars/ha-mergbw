"""MeRGBW Light Integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components.bluetooth import async_ble_device_from_address

from .const import DOMAIN
from .protocol import MeRGBWDevice

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MeRGBW from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    address = entry.data["address"]
    device_type = entry.data.get("device_type", 2)
    
    # Get BLE device from address
    ble_device = async_ble_device_from_address(hass, address, connectable=True)
    if not ble_device:
        _LOGGER.error("Could not find BLE device with address %s", address)
        return False
    
    device = MeRGBWDevice(ble_device, device_type)
    hass.data[DOMAIN][entry.entry_id] = device
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        device: MeRGBWDevice = hass.data[DOMAIN].pop(entry.entry_id)
        await device.disconnect()
    return unload_ok
