"""Tests for the Qolsys Panel valves."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from conftest import PANEL_MAC
import pytest
from qolsys_controller.automation.service_valve import ValveService

from custom_components.qolsys_panel.valve import (
    AutomationDevice_Valve,
    async_setup_entry,
)
from homeassistant.components.valve import ValveEntityFeature
from homeassistant.core import HomeAssistant

UID = PANEL_MAC


@pytest.fixture
def controller() -> MagicMock:
    """A controller mock whose automation device exposes a valve service."""
    c = MagicMock()

    service = MagicMock()
    service.endpoint = 0
    device = MagicMock()
    device.virtual_node_id = "5"
    device.service_get_protocol.return_value = [service]
    c.state.automation_devices = [device]

    # The entity checks isinstance(service, ValveService), so spec the mock.
    c.state.automation_device.return_value.service_get.return_value = MagicMock(
        spec=ValveService
    )
    return c


async def test_async_setup_entry_creates_entities(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup builds a valve per automation-device valve service."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], AutomationDevice_Valve)


def test_supported_features(controller: MagicMock) -> None:
    """All supported valve features are advertised when the service allows."""
    valve = AutomationDevice_Valve(controller, "5", 0, UID)
    features = valve.supported_features
    assert features & ValveEntityFeature.OPEN
    assert features & ValveEntityFeature.CLOSE
    assert features & ValveEntityFeature.STOP
    assert features & ValveEntityFeature.SET_POSITION
    assert valve.reports_position is True


def test_is_closed(controller: MagicMock) -> None:
    """The valve reports the service closed state."""
    valve = AutomationDevice_Valve(controller, "5", 0, UID)
    valve._service.is_closed = True
    assert valve.is_closed is True
    valve._service.is_closed = False
    assert valve.is_closed is False


@pytest.mark.parametrize(
    ("method", "args", "service_call"),
    [
        ("async_open_valve", (), "open"),
        ("async_close_valve", (), "close"),
        ("async_stop_valve", (), "stop"),
        ("async_set_valve_position", (40,), "set_position"),
    ],
)
async def test_valve_commands(
    controller: MagicMock, method: str, args: tuple[Any, ...], service_call: str
) -> None:
    """Valve commands forward to the backing service."""
    valve = AutomationDevice_Valve(controller, "5", 0, UID)
    setattr(valve._service, service_call, AsyncMock())

    await getattr(valve, method)(*args)

    getattr(valve._service, service_call).assert_awaited_once()
