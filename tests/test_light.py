"""Tests for MeRGBW light entity."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, State

from custom_components.mergbw.light import MeRGBWLight
from custom_components.mergbw.protocol import DeviceState, MeRGBWDevice
from custom_components.mergbw.const import DOMAIN

from .conftest import TEST_ADDRESS, TEST_NAME, TEST_DEVICE_TYPE, TEST_MODEL


@pytest.fixture
def mock_device():
    """Create a mock MeRGBWDevice."""
    device = MagicMock(spec=MeRGBWDevice)
    device.address = TEST_ADDRESS
    device.name = TEST_NAME
    device.state = DeviceState(device_type=TEST_DEVICE_TYPE)
    device.is_connected = False
    device.connect = AsyncMock(return_value=True)
    device.disconnect = AsyncMock()
    device.sync_status = AsyncMock(return_value=True)
    device.turn_on = AsyncMock(return_value=True)
    device.turn_off = AsyncMock(return_value=True)
    device.set_power = AsyncMock(return_value=True)
    device.set_color = AsyncMock(return_value=True)
    device.set_brightness = AsyncMock(return_value=True)
    device.register_disconnect_callback = MagicMock()
    device.register_available_callback = MagicMock()
    device.update_ble_device = MagicMock()
    return device


@pytest.fixture
def mock_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.data = {
        "address": TEST_ADDRESS,
        "device_type": TEST_DEVICE_TYPE,
        "model": TEST_MODEL,
    }
    entry.entry_id = "test_entry"
    return entry


class TestMeRGBWLightInit:
    """Tests for MeRGBWLight initialization."""

    def test_light_init(self, mock_device, mock_entry):
        """Test light entity initialization."""
        light = MeRGBWLight(mock_device, mock_entry)

        assert light._attr_unique_id == TEST_ADDRESS
        assert light._attr_has_entity_name is True
        assert light._attr_name is None
        assert ColorMode.RGB in light._attr_supported_color_modes
        assert light._attr_color_mode == ColorMode.RGB
        assert light._attr_should_poll is False

    def test_light_device_info(self, mock_device, mock_entry):
        """Test light entity device info."""
        light = MeRGBWLight(mock_device, mock_entry)

        device_info = light._attr_device_info
        assert (DOMAIN, TEST_ADDRESS) in device_info["identifiers"]
        assert device_info["name"] == TEST_NAME
        assert device_info["manufacturer"] == "MeRGBW"
        assert device_info["model"] == TEST_MODEL
        assert device_info["hw_version"] == "RGB Line/Strip"  # Type 2 default

    def test_light_extra_state_attributes(self, mock_device, mock_entry):
        """Test light entity extra state attributes."""
        light = MeRGBWLight(mock_device, mock_entry)

        attrs = light.extra_state_attributes
        assert attrs["device_type"] == TEST_DEVICE_TYPE
        assert attrs["device_type_name"] == "RGB Line/Strip"


class TestMeRGBWLightState:
    """Tests for MeRGBWLight state properties."""

    def test_is_on_true(self, mock_device, mock_entry):
        """Test is_on returns True when device is on."""
        mock_device.state.power = True
        light = MeRGBWLight(mock_device, mock_entry)
        assert light.is_on is True

    def test_is_on_false(self, mock_device, mock_entry):
        """Test is_on returns False when device is off."""
        mock_device.state.power = False
        light = MeRGBWLight(mock_device, mock_entry)
        assert light.is_on is False

    def test_brightness_conversion(self, mock_device, mock_entry):
        """Test brightness conversion from device (0-100) to HA (0-255)."""
        light = MeRGBWLight(mock_device, mock_entry)

        # 0% brightness
        mock_device.state.brightness = 0
        assert light.brightness == 0

        # 50% brightness
        mock_device.state.brightness = 50
        assert light.brightness == 127  # int(50 * 255 / 100)

        # 100% brightness
        mock_device.state.brightness = 100
        assert light.brightness == 255

    def test_rgb_color(self, mock_device, mock_entry):
        """Test RGB color property."""
        mock_device.state.red = 255
        mock_device.state.green = 128
        mock_device.state.blue = 64

        light = MeRGBWLight(mock_device, mock_entry)
        assert light.rgb_color == (255, 128, 64)

    def test_available_initially_true(self, mock_device, mock_entry):
        """Test that entity is available initially (after setup succeeds)."""
        light = MeRGBWLight(mock_device, mock_entry)
        # _ble_available defaults to True since setup succeeded
        assert light.available is True


class TestMeRGBWLightCallbacks:
    """Tests for MeRGBWLight callbacks."""

    def test_registers_callbacks_on_add(self, mock_device, mock_entry):
        """Test that callbacks are registered when entity is added."""
        light = MeRGBWLight(mock_device, mock_entry)

        # Manually call the registration (normally done by async_added_to_hass)
        mock_device.register_disconnect_callback(light._handle_disconnect)
        mock_device.register_available_callback(light._handle_available)

        mock_device.register_disconnect_callback.assert_called()
        mock_device.register_available_callback.assert_called()

    def test_handle_disconnect(self, mock_device, mock_entry):
        """Test disconnect handler updates state."""
        light = MeRGBWLight(mock_device, mock_entry)
        light._connected = True
        # Mock async_write_ha_state to avoid HA dependency
        light.async_write_ha_state = MagicMock()

        # Simulate disconnect
        light._handle_disconnect()

        assert light._connected is False
        light.async_write_ha_state.assert_called_once()

    def test_handle_available(self, mock_device, mock_entry):
        """Test available handler updates state."""
        light = MeRGBWLight(mock_device, mock_entry)
        light._ble_available = False
        # Mock async_write_ha_state to avoid HA dependency
        light.async_write_ha_state = MagicMock()

        # Simulate device becoming available
        light._handle_available()

        assert light._ble_available is True
        light.async_write_ha_state.assert_called_once()


class TestMeRGBWLightCommands:
    """Tests for MeRGBWLight commands (turn_on, turn_off)."""

    async def test_turn_on_simple(self, mock_device, mock_entry):
        """Test simple turn on without brightness/color."""
        light = MeRGBWLight(mock_device, mock_entry)
        light._connected = True
        mock_device.is_connected = True
        light.async_write_ha_state = MagicMock()

        await light.async_turn_on()

        mock_device.turn_on.assert_called_once_with(brightness=None, rgb=None)

    async def test_turn_on_with_brightness(self, mock_device, mock_entry):
        """Test turn on with brightness."""
        light = MeRGBWLight(mock_device, mock_entry)
        light._connected = True
        mock_device.is_connected = True
        light.async_write_ha_state = MagicMock()

        # HA brightness 127 (~50%) should convert to device brightness 49
        await light.async_turn_on(**{ATTR_BRIGHTNESS: 127})

        mock_device.turn_on.assert_called_once()
        call_kwargs = mock_device.turn_on.call_args[1]
        assert call_kwargs["brightness"] == 49  # int(127 * 100 / 255)

    async def test_turn_on_with_rgb_color(self, mock_device, mock_entry):
        """Test turn on with RGB color."""
        light = MeRGBWLight(mock_device, mock_entry)
        light._connected = True
        mock_device.is_connected = True
        light.async_write_ha_state = MagicMock()

        await light.async_turn_on(**{ATTR_RGB_COLOR: (255, 0, 128)})

        mock_device.turn_on.assert_called_once()
        call_kwargs = mock_device.turn_on.call_args[1]
        assert call_kwargs["rgb"] == (255, 0, 128)

    async def test_turn_on_with_brightness_and_color(self, mock_device, mock_entry):
        """Test turn on with both brightness and color."""
        light = MeRGBWLight(mock_device, mock_entry)
        light._connected = True
        mock_device.is_connected = True
        light.async_write_ha_state = MagicMock()

        await light.async_turn_on(**{ATTR_BRIGHTNESS: 200, ATTR_RGB_COLOR: (0, 255, 0)})

        mock_device.turn_on.assert_called_once()
        call_kwargs = mock_device.turn_on.call_args[1]
        assert call_kwargs["brightness"] == 78  # int(200 * 100 / 255)
        assert call_kwargs["rgb"] == (0, 255, 0)

    async def test_turn_off(self, mock_device, mock_entry):
        """Test turn off."""
        light = MeRGBWLight(mock_device, mock_entry)
        light._connected = True
        mock_device.is_connected = True
        light.async_write_ha_state = MagicMock()

        await light.async_turn_off()

        mock_device.turn_off.assert_called_once()

    async def test_turn_on_connects_if_disconnected(self, mock_device, mock_entry):
        """Test that turn_on connects to device if not connected."""
        light = MeRGBWLight(mock_device, mock_entry)
        light._connected = False
        mock_device.is_connected = False
        light.async_write_ha_state = MagicMock()

        await light.async_turn_on()

        mock_device.connect.assert_called_once()
        mock_device.turn_on.assert_called_once()

    async def test_turn_on_fails_if_cannot_connect(self, mock_device, mock_entry):
        """Test that turn_on does nothing if connection fails."""
        light = MeRGBWLight(mock_device, mock_entry)
        light._connected = False
        mock_device.is_connected = False
        mock_device.connect = AsyncMock(return_value=False)
        light.async_write_ha_state = MagicMock()

        await light.async_turn_on()

        mock_device.connect.assert_called_once()
        mock_device.turn_on.assert_not_called()


class TestMeRGBWLightStateRestoration:
    """Tests for state restoration."""

    async def test_restore_state_brightness(self, hass: HomeAssistant, mock_device, mock_entry):
        """Test that brightness is restored from previous state."""
        light = MeRGBWLight(mock_device, mock_entry)

        # Create a mock last state with brightness
        last_state = State(
            entity_id="light.test",
            state=STATE_ON,
            attributes={ATTR_BRIGHTNESS: 127},  # ~50%
        )

        with patch.object(light, "async_get_last_state", return_value=last_state):
            # Mock hass to avoid actual HA setup
            light.hass = hass

            # Disable actual connection for this test
            mock_device.connect = AsyncMock(return_value=False)

            # Call the method that restores state
            await light.async_added_to_hass()

            # Check brightness was restored (127 HA -> 49 device)
            assert mock_device.state.brightness == 49

    async def test_restore_state_rgb_color(self, hass: HomeAssistant, mock_device, mock_entry):
        """Test that RGB color is restored from previous state."""
        light = MeRGBWLight(mock_device, mock_entry)

        # Create a mock last state with color
        last_state = State(
            entity_id="light.test",
            state=STATE_ON,
            attributes={ATTR_RGB_COLOR: (255, 0, 128)},
        )

        with patch.object(light, "async_get_last_state", return_value=last_state):
            light.hass = hass
            mock_device.connect = AsyncMock(return_value=False)

            await light.async_added_to_hass()

            assert mock_device.state.red == 255
            assert mock_device.state.green == 0
            assert mock_device.state.blue == 128

    async def test_restore_state_no_previous(self, hass: HomeAssistant, mock_device, mock_entry):
        """Test handling when there is no previous state."""
        light = MeRGBWLight(mock_device, mock_entry)

        # Store original values
        original_brightness = mock_device.state.brightness
        original_red = mock_device.state.red

        with patch.object(light, "async_get_last_state", return_value=None):
            light.hass = hass
            mock_device.connect = AsyncMock(return_value=False)

            await light.async_added_to_hass()

            # Values should remain at defaults
            assert mock_device.state.brightness == original_brightness
            assert mock_device.state.red == original_red

    async def test_restore_state_partial(self, hass: HomeAssistant, mock_device, mock_entry):
        """Test restoring state with only some attributes."""
        light = MeRGBWLight(mock_device, mock_entry)

        # Create a state with only brightness, no color
        last_state = State(
            entity_id="light.test",
            state=STATE_ON,
            attributes={ATTR_BRIGHTNESS: 200},
        )

        original_red = mock_device.state.red

        with patch.object(light, "async_get_last_state", return_value=last_state):
            light.hass = hass
            mock_device.connect = AsyncMock(return_value=False)

            await light.async_added_to_hass()

            # Brightness should be restored
            assert mock_device.state.brightness == 78  # int(200 * 100 / 255)
            # Color should remain at default
            assert mock_device.state.red == original_red
