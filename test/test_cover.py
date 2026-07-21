"""Tests for the Qolsys Panel covers."""

from unittest.mock import AsyncMock, MagicMock

from conftest import PANEL_MAC
import pytest

from custom_components.qolsys_panel.cover import (
    AutomationDevice_Cover,
    async_setup_entry,
)
from homeassistant.components.cover import CoverEntityFeature
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
    """Setup builds a cover per automation-device cover service."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], AutomationDevice_Cover)


def test_supported_features(controller: MagicMock) -> None:
    """All supported cover features are advertised when the service allows."""
    cover = AutomationDevice_Cover(controller, "5", 0, UID)
    features = cover.supported_features
    assert features & CoverEntityFeature.OPEN
    assert features & CoverEntityFeature.CLOSE
    assert features & CoverEntityFeature.STOP
    assert features & CoverEntityFeature.SET_POSITION


@pytest.mark.parametrize("prop", ["is_closed", "is_closing", "is_opening"])
def test_cover_state_properties(controller: MagicMock, prop: str) -> None:
    """Each cover state property reflects the backing service."""
    cover = AutomationDevice_Cover(controller, "5", 0, UID)
    setattr(cover._cover, prop, True)
    assert getattr(cover, prop) is True


async def test_open_close(controller: MagicMock) -> None:
    """Open and close forward to the backing service."""
    cover = AutomationDevice_Cover(controller, "5", 0, UID)
    cover._cover.open = AsyncMock()
    cover._cover.close = AsyncMock()

    await cover.async_open_cover()
    cover._cover.open.assert_awaited_once()

    await cover.async_close_cover()
    cover._cover.close.assert_awaited_once()


async def test_set_position(controller: MagicMock) -> None:
    """Setting a position forwards it; a missing position is ignored."""
    cover = AutomationDevice_Cover(controller, "5", 0, UID)
    cover._cover.set_position = AsyncMock()

    await cover.set_current_position(position=40)
    cover._cover.set_position.assert_awaited_once_with(40)

    await cover.set_current_position()
    cover._cover.set_position.assert_awaited_once()
