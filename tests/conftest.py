"""Fixtures for MeRGBW tests."""
from __future__ import annotations

import sys
from pathlib import Path

# Add the repo root to sys.path so the mergbw package can be imported.
# This works whether the repo is:
#   1. Cloned standalone as `mergbw/` (tests run from repo root)
#   2. Inside a HA config at `custom_components/mergbw/`
#
# Structure: tests/conftest.py -> mergbw (repo root)
REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT.parent))

# Also support the custom_components structure for HA development
CUSTOM_COMPONENTS_DIR = REPO_ROOT.parent
if CUSTOM_COMPONENTS_DIR.name == "custom_components":
    HA_CONFIG_DIR = CUSTOM_COMPONENTS_DIR.parent
    if str(HA_CONFIG_DIR) not in sys.path:
        sys.path.insert(0, str(HA_CONFIG_DIR))

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

# Import from the package - works as both `mergbw` and `custom_components.mergbw`
try:
    from custom_components.mergbw.const import DOMAIN
except ImportError:
    from mergbw.const import DOMAIN

# Test device constants
TEST_ADDRESS = "AA:BB:CC:DD:EE:FF"
TEST_NAME = "MeRGBW Test Light"
TEST_MODEL = "TG201"
TEST_DEVICE_TYPE = 2  # RGB Line/Strip

# MeRGBW service UUID (discovery signature)
MERGBW_SERVICE_UUID = "00003519-0000-1000-8000-00805f9b34fb"


def _make_ble_device(address: str, name: str) -> BLEDevice:
    """Create a BLEDevice."""
    return BLEDevice(address, name, {})


def _make_service_info(
    address: str,
    name: str,
    manufacturer_data: dict[int, bytes],
    service_uuids: list[str],
) -> BluetoothServiceInfoBleak:
    """Create a BluetoothServiceInfoBleak using the factory method."""
    device = _make_ble_device(address, name)
    adv_data = AdvertisementData(
        local_name=name,
        manufacturer_data=manufacturer_data,
        service_data={},
        service_uuids=service_uuids,
        tx_power=None,
        rssi=-60,
        platform_data=(),
    )
    return BluetoothServiceInfoBleak.from_device_and_advertisement_data(
        device, adv_data, "local", 0, True
    )


@pytest.fixture
def mock_ble_device() -> BLEDevice:
    """Create a mock BLE device."""
    return _make_ble_device(TEST_ADDRESS, TEST_NAME)


@pytest.fixture
def mock_service_info() -> BluetoothServiceInfoBleak:
    """Create a mock BluetoothServiceInfoBleak for discovery."""
    # Build manufacturer data with device type at byte 8 and model at bytes 9-18
    # Format: 8 bytes reserved + 1 byte device type + 10 bytes model
    mfr_data = bytearray(19)
    mfr_data[8] = TEST_DEVICE_TYPE
    model_bytes = TEST_MODEL.encode("ascii")
    mfr_data[9 : 9 + len(model_bytes)] = model_bytes

    return _make_service_info(
        TEST_ADDRESS,
        TEST_NAME,
        {0xFFFF: bytes(mfr_data)},
        [MERGBW_SERVICE_UUID],
    )


@pytest.fixture
def mock_service_info_not_mergbw() -> BluetoothServiceInfoBleak:
    """Create a mock BluetoothServiceInfoBleak for a non-MeRGBW device."""
    return _make_service_info(
        "11:22:33:44:55:66",
        "Other Device",
        {},
        ["0000180a-0000-1000-8000-00805f9b34fb"],  # Some other UUID
    )


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.data = {
        CONF_ADDRESS: TEST_ADDRESS,
        "device_type": TEST_DEVICE_TYPE,
        "model": TEST_MODEL,
    }
    entry.entry_id = "test_entry_id"
    entry.unique_id = TEST_ADDRESS
    entry.title = TEST_NAME
    return entry


@pytest.fixture
def mock_bleak_client() -> Generator[MagicMock, None, None]:
    """Mock BleakClient for connection tests."""
    with patch(
        "custom_components.mergbw.protocol.establish_connection"
    ) as mock_establish:
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.services = []
        mock_client.start_notify = AsyncMock()
        mock_client.write_gatt_char = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_establish.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_bluetooth(enable_bluetooth: None) -> Generator[None, None, None]:
    """Auto mock bluetooth."""
    yield


# Enable custom integrations fixture (required for pytest-homeassistant-custom-component)
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None, None, None]:
    """Enable custom integrations."""
    yield
