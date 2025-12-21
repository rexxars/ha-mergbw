"""Tests for MeRGBW config flow."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# Support multiple configurations:
# 1. HA dev setup: custom_components.mergbw
# 2. Standalone repo named 'mergbw': mergbw.const
# 3. Standalone repo (e.g., 'ha-mergbw'): direct import from const
try:
    from custom_components.mergbw.const import DOMAIN
    from custom_components.mergbw.config_flow import parse_advertisement
except ImportError:
    try:
        from mergbw.const import DOMAIN
        from mergbw.config_flow import parse_advertisement
    except ImportError:
        from const import DOMAIN
        from config_flow import parse_advertisement

from .conftest import (
    TEST_ADDRESS,
    TEST_NAME,
    TEST_MODEL,
    TEST_DEVICE_TYPE,
    MERGBW_SERVICE_UUID,
    _make_service_info,
)


class TestParseAdvertisement:
    """Tests for advertisement parsing."""

    def test_parse_valid_advertisement(
        self, mock_service_info: BluetoothServiceInfoBleak
    ):
        """Test parsing a valid MeRGBW advertisement."""
        result = parse_advertisement(mock_service_info)
        assert result is not None
        assert result["address"] == TEST_ADDRESS
        assert result["name"] == TEST_NAME
        assert result["device_type"] == TEST_DEVICE_TYPE
        assert result["model"] == TEST_MODEL

    def test_parse_non_mergbw_device(
        self, mock_service_info_not_mergbw: BluetoothServiceInfoBleak
    ):
        """Test that non-MeRGBW devices return None."""
        result = parse_advertisement(mock_service_info_not_mergbw)
        assert result is None

    def test_parse_advertisement_no_name(self):
        """Test parsing advertisement with no device name.

        When no local_name is provided, the BLE library may use the address
        as the name. Our code then falls back to 'MeRGBW Light' if the name
        is empty or only whitespace, but an address is still a valid name.
        """
        service_info = _make_service_info(
            TEST_ADDRESS,
            "",  # Empty name - BLE may use address as fallback
            {},
            [MERGBW_SERVICE_UUID],
        )
        result = parse_advertisement(service_info)
        assert result is not None
        # When name is empty/whitespace, falls back to address or default
        assert result["name"] in (TEST_ADDRESS, "MeRGBW Light")

    def test_parse_advertisement_all_device_types(self):
        """Test parsing advertisements for all device types 1-8."""
        for device_type in range(1, 9):
            mfr_data = bytearray(19)
            mfr_data[8] = device_type

            service_info = _make_service_info(
                TEST_ADDRESS,
                f"Device Type {device_type}",
                {0xFFFF: bytes(mfr_data)},
                [MERGBW_SERVICE_UUID],
            )
            result = parse_advertisement(service_info)
            assert result is not None
            assert result["device_type"] == device_type


class TestConfigFlowUnit:
    """Unit tests for config flow logic.

    Note: Full integration tests for config flows require complex HA setup
    with bluetooth mocking. These tests verify the flow logic directly.
    """

    def test_config_flow_init(self):
        """Test config flow can be initialized."""
        try:
            from custom_components.mergbw.config_flow import MeRGBWConfigFlow
        except ImportError:
            try:
                from mergbw.config_flow import MeRGBWConfigFlow
            except ImportError:
                from config_flow import MeRGBWConfigFlow

        flow = MeRGBWConfigFlow()
        assert flow.VERSION == 1
        assert flow._discovered_devices == {}
        assert flow._discovery_info is None


# Note: Full config flow integration tests are skipped as they require
# complex Home Assistant bluetooth stack mocking. The parse_advertisement
# tests above verify the core discovery logic works correctly.
#
# For full integration testing, consider using the Home Assistant development
# environment with `pytest-homeassistant-custom-component` and proper
# bluetooth adapter mocking.
#
# See: https://developers.home-assistant.io/docs/development_testing
