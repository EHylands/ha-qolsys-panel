"""Support for Qolsys Panel Central Scene events."""

from __future__ import annotations

from typing import cast

from qolsys_controller import qolsys_controller
from qolsys_controller.automation.service_central_scene import CentralSceneService
from qolsys_controller.enum_qolsys import QolsysNotification
from qolsys_controller.observable import Event

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysAutomationDeviceEntity, QolsysIpCameraEntity
from .types import QolsysPanelConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Central Scene events."""
    QolsysPanel = config_entry.runtime_data
    if (unique_id := config_entry.unique_id) is None:
        raise ConfigEntryError("Config entry has no unique_id; re-add the integration")

    entities: list[EventEntity] = []

    # One event entity per scene (button) of every automation-device Central
    # Scene service.
    for device in QolsysPanel.state.automation_devices:
        for base_service in device.service_get_protocol(CentralSceneService):
            service = cast(CentralSceneService, base_service)
            for scene_number, central_scene in service.scenes.items():
                if not central_scene.supported:
                    continue
                entities.append(
                    AutomationDeviceCentralSceneEvent(
                        QolsysPanel,
                        device.virtual_node_id,
                        service.endpoint,
                        scene_number,
                        unique_id,
                    )
                )

    # One motion and one doorbell (key-press) event entity per IP camera.
    for camera in QolsysPanel.state.ip_cameras:
        entities.append(
            QolsysIpCameraMotionEvent(QolsysPanel, camera.camera_id, unique_id)
        )
        entities.append(
            QolsysIpCameraDoorbellEvent(QolsysPanel, camera.camera_id, unique_id)
        )

    async_add_entities(entities)


class AutomationDeviceCentralSceneEvent(QolsysAutomationDeviceEntity, EventEntity):
    """Automation Device Central Scene Event Entity.

    A single scene (button) on a Central Scene endpoint. Stateless: each key
    press reported by the panel fires the matching event type (single_tap,
    double_tap, hold, release, ...).
    """

    _attr_device_class = EventDeviceClass.BUTTON

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        virtual_node_id: str,
        endpoint: int,
        scene_number: int,
        unique_id: str,
    ) -> None:
        super().__init__(QolsysPanel, virtual_node_id, unique_id)
        self._endpoint = endpoint
        self._scene_number = scene_number
        self._attr_unique_id = (
            f"{self._autdev_unique_id}_central_scene{endpoint}_scene{scene_number}"
        )
        service = self._autdev.service_get(CentralSceneService, endpoint)
        assert service is not None
        self._service: CentralSceneService = service
        self._attr_event_types = self._service.scenes[scene_number].supported
        self._attr_name = (
            f"Scene {scene_number}{'' if endpoint == 0 else f' Endpoint {endpoint}'}"
        )

    @callback
    def _handle_scene_event(self, event: Event) -> None:
        """Fire the Home Assistant event when this scene reports a key press."""
        data = event.data
        if (
            data.get("endpoint") != self._endpoint
            or data.get("scene_number") != self._scene_number
        ):
            return

        event_type = data.get("event")
        if event_type is None:
            return

        self._trigger_event(event_type, {"sequence": data.get("sequence")})
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Observe scene events."""
        await super().async_added_to_hass()
        self._autdev.register(
            QolsysNotification.AUTOMATION_CENTRAL_SCENE_EVENT, self._handle_scene_event
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing scene events."""
        await super().async_will_remove_from_hass()
        self._autdev.unregister(
            QolsysNotification.AUTOMATION_CENTRAL_SCENE_EVENT, self._handle_scene_event
        )


class QolsysIpCameraMotionEvent(QolsysIpCameraEntity, EventEntity):
    """Event entity fired by an IP (doorbell) camera motion event.

    Camera motion events are stateless pulses: each motion report from the
    camera fires a ``motion`` event.
    """

    _attr_device_class = EventDeviceClass.MOTION
    _attr_event_types = ["motion"]
    _attr_translation_key = "camera_motion"

    def __init__(
        self, QolsysPanel: qolsys_controller, camera_id: str, unique_id: str
    ) -> None:
        """Set up an IP camera motion event entity."""
        super().__init__(QolsysPanel, camera_id, unique_id)
        self._attr_unique_id = f"{self._camera_unique_id}_motion_event"

    @callback
    def _handle_motion_event(self, event: Event) -> None:
        """Fire the Home Assistant event when the camera reports motion."""
        self._trigger_event("motion", event.data)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Observe the camera motion event."""
        await super().async_added_to_hass()
        self._camera.register(
            QolsysNotification.CAMERA_MOTION_EVENT, self._handle_motion_event
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing the camera motion event."""
        await super().async_will_remove_from_hass()
        self._camera.unregister(
            QolsysNotification.CAMERA_MOTION_EVENT, self._handle_motion_event
        )


class QolsysIpCameraDoorbellEvent(QolsysIpCameraEntity, EventEntity):
    """Event entity fired by an IP (doorbell) camera key-press event.

    Camera press events are stateless pulses: each key press reported by the
    camera fires a ``pressed`` event.
    """

    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_event_types = ["pressed"]
    _attr_translation_key = "camera_doorbell"

    def __init__(
        self, QolsysPanel: qolsys_controller, camera_id: str, unique_id: str
    ) -> None:
        """Set up an IP camera doorbell event entity."""
        super().__init__(QolsysPanel, camera_id, unique_id)
        self._attr_unique_id = f"{self._camera_unique_id}_doorbell_event"

    @callback
    def _handle_press_event(self, event: Event) -> None:
        """Fire the Home Assistant event when the camera reports a key press."""
        self._trigger_event("pressed", event.data)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Observe the camera key-press event."""
        await super().async_added_to_hass()
        self._camera.register(
            QolsysNotification.CAMERA_PRESS_EVENT, self._handle_press_event
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing the camera key-press event."""
        await super().async_will_remove_from_hass()
        self._camera.unregister(
            QolsysNotification.CAMERA_PRESS_EVENT, self._handle_press_event
        )
