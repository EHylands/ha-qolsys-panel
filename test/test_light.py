"""Tests for the Qolsys Panel lights."""

from unittest.mock import AsyncMock, MagicMock

from conftest import PANEL_MAC
import pytest

from custom_components.qolsys_panel.light import (
    AutomationDevice_Light,
    async_setup_entry,
    to_hass_level,
    to_qolsys_level,
)
from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode
from homeassistant.core import HomeAssistant

UID = PANEL_MAC


@pytest.fixture
def controller() -> MagicMock:
    """A controller mock with one automation device."""
    c = MagicMock()
    service = MagicMock()
    service.endpoint = 0
    device = MagicMock()
    device.virtual_node_id = "5"
    device.service_get_protocol.return_value = [service]
    c.state.automation_devices = [device]
    return c


def test_level_conversions() -> None:
    """Level conversion helpers map between Home Assistant and Qolsys ranges."""
    assert to_qolsys_level(255) == 99
    assert to_qolsys_level(0) == 0
    assert to_hass_level(99) == 255
    assert to_hass_level(0) == 0


async def test_async_setup_entry_creates_entities(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup builds a light per automation-device light service."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], AutomationDevice_Light)


@pytest.mark.parametrize(
    ("supports_level", "color_mode"),
    [(True, ColorMode.BRIGHTNESS), (False, ColorMode.ONOFF)],
)
def test_color_mode(
    controller: MagicMock, supports_level: bool, color_mode: ColorMode
) -> None:
    """Color mode depends on whether the device supports dimming."""
    service = controller.state.automation_device.return_value.service_get.return_value
    service.supports_level.return_value = supports_level

    light = AutomationDevice_Light(controller, "5", 0, UID)

    assert light._attr_color_mode == color_mode


def test_is_on_and_brightness(controller: MagicMock) -> None:
    """The light reports the service on state and scaled brightness."""
    light = AutomationDevice_Light(controller, "5", 0, UID)
    light._service.is_on = True
    light._service.level = 99
    assert light.is_on is True
    assert light.brightness == 255


async def test_turn_on_without_brightness(controller: MagicMock) -> None:
    """Turning on without brightness calls the plain turn_on."""
    light = AutomationDevice_Light(controller, "5", 0, UID)
    light._service.turn_on = AsyncMock()
    await light.async_turn_on()
    light._service.turn_on.assert_awaited_once()


async def test_turn_on_with_brightness(controller: MagicMock) -> None:
    """Turning on with brightness converts and calls set_level."""
    light = AutomationDevice_Light(controller, "5", 0, UID)
    light._service.set_level = AsyncMock()
    await light.async_turn_on(**{ATTR_BRIGHTNESS: 255})
    light._service.set_level.assert_awaited_once_with(99)


async def test_turn_off(controller: MagicMock) -> None:
    """Turning off calls the service turn_off."""
    light = AutomationDevice_Light(controller, "5", 0, UID)
    light._service.turn_off = AsyncMock()
    await light.async_turn_off()
    light._service.turn_off.assert_awaited_once()
