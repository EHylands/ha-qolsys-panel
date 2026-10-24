"""Tests for the Qolsys Panel Central Scene events."""

from collections import Counter
from typing import Any, NamedTuple, cast
from unittest.mock import MagicMock

from conftest import PANEL_MAC
import pytest
from qolsys_controller.automation.service_central_scene import CentralScene
from qolsys_controller.enum_qolsys import QolsysNotification
from qolsys_controller.observable import Event

from custom_components.qolsys_panel.event import (
    AutomationDeviceCentralSceneEvent,
    QolsysIpCameraDoorbellEvent,
    QolsysIpCameraMotionEvent,
    async_setup_entry,
)
from homeassistant.components.event import (
    DoorbellEventType,
    EventDeviceClass,
    EventEntityStateAttribute,
)
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

    camera = MagicMock()
    camera.camera_id = "100"
    camera.camera_name = "Front Door"
    c.state.ip_cameras = [camera]

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


async def test_async_setup_entry_creates_expected_entities(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """One entity per supported scene plus motion/doorbell events per camera."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    # Scenes 1 and 2 have supported events (scene 3 is skipped) + 2 camera events.
    assert len(entities) == 4
    counts = Counter(type(e).__name__ for e in entities)
    assert counts["AutomationDeviceCentralSceneEvent"] == 2
    assert counts["QolsysIpCameraMotionEvent"] == 1
    assert counts["QolsysIpCameraDoorbellEvent"] == 1


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


class _CameraEventCase(NamedTuple):
    """Parametrization bundle describing one IP camera event entity."""

    cls: type
    handler: str
    notification: QolsysNotification
    device_class: EventDeviceClass
    event_type: str
    suffix: str


_CAMERA_EVENT_CASES = [
    _CameraEventCase(
        QolsysIpCameraMotionEvent,
        "_handle_motion_event",
        QolsysNotification.CAMERA_MOTION_EVENT,
        EventDeviceClass.MOTION,
        "motion",
        "_motion_event",
    ),
    _CameraEventCase(
        QolsysIpCameraDoorbellEvent,
        "_handle_press_event",
        QolsysNotification.CAMERA_PRESS_EVENT,
        EventDeviceClass.DOORBELL,
        DoorbellEventType.RING,
        "_doorbell_event",
    ),
]


@pytest.mark.parametrize("case", _CAMERA_EVENT_CASES, ids=lambda c: c.cls.__name__)
class TestIpCameraEvents:
    """Shared behaviour of the two IP camera event entities."""

    def test_attributes(self, controller: MagicMock, case: _CameraEventCase) -> None:
        """The entity advertises its device class, event type and unique id."""
        event = case.cls(controller, "100", UID)
        assert event.device_class == case.device_class
        assert event.event_types == [case.event_type]
        assert event.unique_id is not None
        assert event.unique_id.endswith(case.suffix)
        assert event.state is None

    def test_handle_event_fires(
        self, controller: MagicMock, case: _CameraEventCase
    ) -> None:
        """A camera notification triggers the matching event type."""
        event = case.cls(controller, "100", UID)
        event.async_write_ha_state = MagicMock()

        getattr(event, case.handler)(
            Event(case.notification, MagicMock(), {"camera_id": "100"})
        )

        event.async_write_ha_state.assert_called_once()
        attributes = event.state_attributes
        assert attributes[EventEntityStateAttribute.EVENT_TYPE] == case.event_type

    async def test_register_unregister(
        self, controller: MagicMock, case: _CameraEventCase
    ) -> None:
        """The entity subscribes/unsubscribes to its camera event."""
        event = case.cls(controller, "100", UID)
        callback = getattr(event, case.handler)

        await event.async_added_to_hass()
        cast(MagicMock, event._camera).register.assert_any_call(
            case.notification, callback
        )

        await event.async_will_remove_from_hass()
        cast(MagicMock, event._camera).unregister.assert_any_call(
            case.notification, callback
        )
