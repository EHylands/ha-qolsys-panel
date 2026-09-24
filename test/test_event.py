"""Tests for the Qolsys Panel Central Scene events."""

from typing import Any
from unittest.mock import MagicMock

from conftest import PANEL_MAC
import pytest
from qolsys_controller.automation.service_central_scene import CentralScene
from qolsys_controller.enum_qolsys import QolsysNotification
from qolsys_controller.observable import Event

from custom_components.qolsys_panel.event import (
    AutomationDeviceCentralSceneEvent,
    async_setup_entry,
)
from homeassistant.components.event import EventDeviceClass, EventEntityStateAttribute
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

UID = PANEL_MAC


def _scene(number: int, supported: list[str]) -> CentralScene:
    """Build a CentralScene with the given supported event names."""
    scene = CentralScene(number)
    scene.supported = supported
    return scene


@pytest.fixture
def controller() -> MagicMock:
    """A controller whose automation device exposes a Central Scene service."""
    c = MagicMock()

    service = MagicMock()
    service.endpoint = 0
    service.scenes = {
        1: _scene(1, ["single_tap", "double_tap"]),
        2: _scene(2, ["single_tap"]),
        3: _scene(3, []),  # no supported events -> no entity
    }
    service.automation_device.device_name = "Scene Remote"

    device = MagicMock()
    device.virtual_node_id = "7"
    device.service_get_protocol.return_value = [service]
    c.state.automation_devices = [device]

    # The entity re-fetches the service via automation_device().service_get().
    c.state.automation_device.return_value.service_get.return_value = service
    return c


async def test_async_setup_entry_missing_unique_id_raises(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup raises ConfigEntryError when the config entry has no unique_id."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = None
    add_entities = MagicMock()

    with pytest.raises(ConfigEntryError):
        await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_not_called()


async def test_async_setup_entry_creates_one_entity_per_supported_scene(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """One event entity is built per scene that reports supported events."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    # Scenes 1 and 2 have supported events; scene 3 is skipped.
    assert len(entities) == 2
    assert all(isinstance(e, AutomationDeviceCentralSceneEvent) for e in entities)


def test_event_entity_attributes(controller: MagicMock) -> None:
    """The entity advertises its scene's supported event types."""
    event = AutomationDeviceCentralSceneEvent(controller, "7", 0, 1, UID)
    assert event.device_class == EventDeviceClass.BUTTON
    assert event.event_types == ["single_tap", "double_tap"]
    assert event.unique_id is not None
    assert event.unique_id.endswith("_central_scene0_scene1")


def test_handle_scene_event_fires_matching_scene(controller: MagicMock) -> None:
    """A scene notification for this scene triggers the matching event type."""
    event = AutomationDeviceCentralSceneEvent(controller, "7", 0, 1, UID)
    event.async_write_ha_state = MagicMock()

    event._handle_scene_event(
        Event(
            QolsysNotification.AUTOMATION_CENTRAL_SCENE_EVENT,
            MagicMock(),
            {"endpoint": 0, "scene_number": 1, "event": "double_tap", "sequence": 5},
        )
    )

    event.async_write_ha_state.assert_called_once()
    attributes = event.state_attributes
    assert attributes[EventEntityStateAttribute.EVENT_TYPE] == "double_tap"
    assert attributes["sequence"] == 5


@pytest.mark.parametrize(
    "data",
    [
        {"endpoint": 1, "scene_number": 1, "event": "single_tap"},  # other endpoint
        {"endpoint": 0, "scene_number": 2, "event": "single_tap"},  # other scene
        {"endpoint": 0, "scene_number": 1, "event": None},  # no event name
    ],
)
def test_handle_scene_event_ignores_non_matching(
    controller: MagicMock, data: dict[str, Any]
) -> None:
    """Notifications for a different scene/endpoint or without an event are ignored."""
    event = AutomationDeviceCentralSceneEvent(controller, "7", 0, 1, UID)
    event.async_write_ha_state = MagicMock()

    event._handle_scene_event(
        Event(QolsysNotification.AUTOMATION_CENTRAL_SCENE_EVENT, MagicMock(), data)
    )

    event.async_write_ha_state.assert_not_called()
    assert event.state is None
