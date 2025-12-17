"""Config flow for MeRGBW integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, SERVICE_UUID, DEVICE_TYPE_NAMES, ADVERTISEMENT_SIGNATURE

_LOGGER = logging.getLogger(__name__)


def parse_advertisement(service_info: BluetoothServiceInfoBleak) -> dict | None:
    """Parse advertisement data to extract device info."""
    # Check for MeRGBW signature in service UUIDs
    # The protocol doc says to look for [0x19, 0x35] in Type 2 data
    # BLE interprets this as little-endian, so the UUID becomes 0x3519
    MERGBW_UUID = "00003519-0000-1000-8000-00805f9b34fb"

    service_uuids_str = [str(uuid).lower() for uuid in service_info.service_uuids]

    has_mergbw_uuid = (
        MERGBW_UUID.lower() in service_uuids_str or
        SERVICE_UUID.lower() in service_uuids_str
    )

    if not has_mergbw_uuid:
        return None

    # Try to parse manufacturer data for device type and model
    device_type = 2  # Default to RGB Line
    model = ""

    for mfr_id, mfr_data in service_info.manufacturer_data.items():
        _LOGGER.debug(
            "Parsing manufacturer data from mfr_id=%s: length=%d, data=%s",
            mfr_id,
            len(mfr_data),
            mfr_data.hex() if hasattr(mfr_data, 'hex') else mfr_data,
        )

        # The actual format observed from devices:
        # - Bytes 0-7: Device identifier/reserved
        # - Byte 8: Device type (1-8)
        # - Bytes 9-18: Model string (10 bytes, null-padded ASCII)
        #
        # The spec says byte 10 for device type and 11-20 for model,
        # but real devices use bytes 8 and 9-18 respectively.

        # Try byte 8 first (actual observed format)
        if len(mfr_data) > 8:
            potential_device_type = mfr_data[8]
            if 1 <= potential_device_type <= 8:
                device_type = potential_device_type
                # Try to extract model from bytes 9-18
                if len(mfr_data) >= 19:
                    try:
                        model = bytes(mfr_data[9:19]).decode('ascii').strip('\x00 ')
                    except (UnicodeDecodeError, IndexError):
                        model = ""

        # Fallback: try byte 10 (spec format) if byte 8 didn't work
        if device_type == 2 and len(mfr_data) > 10:
            potential_device_type = mfr_data[10]
            if 1 <= potential_device_type <= 8:
                device_type = potential_device_type
                if len(mfr_data) >= 21:
                    try:
                        model = bytes(mfr_data[11:21]).decode('ascii').strip('\x00 ')
                    except (UnicodeDecodeError, IndexError):
                        model = ""

    # Strip null bytes and whitespace from device name
    name = (service_info.name or "").strip('\x00 ') or "MeRGBW Light"

    _LOGGER.debug(
        "Device %s identified as type %d (%s), model: %s",
        name,
        device_type,
        DEVICE_TYPE_NAMES.get(device_type, "Unknown"),
        model or "Unknown",
    )

    return {
        "device_type": device_type,
        "model": model,
        "name": name,
        "address": service_info.address,
    }


class MeRGBWConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MeRGBW."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, dict] = {}
        self._discovery_info: dict | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the Bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        device_info = parse_advertisement(discovery_info)
        if not device_info:
            return self.async_abort(reason="not_supported")

        self._discovery_info = device_info
        name = device_info["name"] or "MeRGBW Light"

        self.context["title_placeholders"] = {
            "name": name
        }

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Bluetooth discovery."""
        if self._discovery_info is None:
            return self.async_abort(reason="not_supported")

        # Skip confirmation dialog and create entry immediately
        return self.async_create_entry(
            title=self._discovery_info["name"] or "MeRGBW Light",
            data={
                CONF_ADDRESS: self._discovery_info["address"],
                "device_type": self._discovery_info["device_type"],
                "model": self._discovery_info["model"],
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            device_info = self._discovered_devices[address]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=device_info["name"] or "MeRGBW Light",
                data={
                    CONF_ADDRESS: address,
                    "device_type": device_info["device_type"],
                    "model": device_info["model"],
                },
            )

        # Discover devices
        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass, connectable=True):
            _LOGGER.debug(
                "Found device: %s (%s) - services: %s, manufacturer_data: %s",
                discovery_info.name,
                discovery_info.address,
                discovery_info.service_uuids,
                discovery_info.manufacturer_data,
            )
            if discovery_info.address in current_addresses:
                continue
            if discovery_info.address in self._discovered_devices:
                continue
            
            device_info = parse_advertisement(discovery_info)
            if device_info:
                self._discovered_devices[discovery_info.address] = device_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        # Build selection list
        devices = {
            address: info["name"] or "MeRGBW Light"
            for address, info in self._discovered_devices.items()
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(devices)}
            ),
        )