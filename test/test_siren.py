"""Tests for the Qolsys Panel sirens."""

from unittest.mock import AsyncMock, MagicMock

from conftest import PANEL_MAC
import pytest

from custom_components.qolsys_panel.siren import (
    AutomationDevice_Siren,
    async_setup_entry,
)
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


async def test_async_setup_entry_creates_entities(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup builds a siren per automation-device siren service."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], AutomationDevice_Siren)


def test_is_on(controller: MagicMock) -> None:
    """The siren reports the service on state."""
    siren = AutomationDevice_Siren(controller, "5", 0, UID)
    siren._service.is_on = True
    assert siren.is_on is True
    siren._service.is_on = False
    assert siren.is_on is False


async def test_turn_on(controller: MagicMock) -> None:
    """Turning the siren on awaits the service turn_on."""
    siren = AutomationDevice_Siren(controller, "5", 0, UID)
    siren._service.turn_on = AsyncMock()
    await siren.async_turn_on()
    siren._service.turn_on.assert_awaited_once()


async def test_turn_off(controller: MagicMock) -> None:
    """Turning the siren off awaits the service turn_off."""
    siren = AutomationDevice_Siren(controller, "5", 0, UID)
    siren._service.turn_off = AsyncMock()
    await siren.async_turn_off()
    siren._service.turn_off.assert_awaited_once()
