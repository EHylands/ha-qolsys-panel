"""Tests for the Qolsys Panel base entities."""

import threading
from typing import cast
from unittest.mock import MagicMock

from conftest import PANEL_MAC
import pytest

from custom_components.qolsys_panel import entity as entity_module
from custom_components.qolsys_panel.const import DOMAIN
from custom_components.qolsys_panel.entity import (
    QolsysAutomationDeviceEntity,
    QolsysPanelEntity,
    QolsysPanelSensorEntity,
    QolsysPartitionEntity,
    QolsysWeatherEntity,
    QolsysZoneEntity,
)
from custom_components.qolsys_panel.vendor.qolsys_controller.enum_qolsys import (
    ControllerState,
    QolsysNotification,
)
from custom_components.qolsys_panel.vendor.qolsys_controller.observable import Event

UID = PANEL_MAC


@pytest.fixture
def controller() -> MagicMock:
    """A generic controller mock."""
    return MagicMock()


@pytest.mark.parametrize(
    ("state", "expected"),
    [(ControllerState.CONNECTED, True), (ControllerState.RECONNECTING, False)],
)
def test_panel_entity_available(
    controller: MagicMock, state: ControllerState, expected: bool
) -> None:
    """The base entity is available only while the controller is connected."""
    controller.controller_state = state
    entity = QolsysPanelEntity(controller, UID)
    assert entity.available is expected


async def test_panel_entity_register_unregister(controller: MagicMock) -> None:
    """The base entity subscribes and unsubscribes to panel status updates."""
    entity = QolsysPanelEntity(controller, UID)

    await entity.async_added_to_hass()
    controller.state.register.assert_any_call(
        QolsysNotification.PANEL_STATUS_UPDATE, entity._handle_update
    )

    await entity.async_will_remove_from_hass()
    controller.state.unregister.assert_any_call(
        QolsysNotification.PANEL_STATUS_UPDATE, entity._handle_update
    )


async def test_partition_entity_register_unregister(controller: MagicMock) -> None:
    """The partition entity subscribes/unsubscribes to partition updates."""
    entity = QolsysPartitionEntity(controller, "1", UID)

    await entity.async_added_to_hass()
    cast(MagicMock, entity._partition).register.assert_any_call(
        QolsysNotification.PARTITION_UPDATE, entity._handle_update
    )

    await entity.async_will_remove_from_hass()
    cast(MagicMock, entity._partition).unregister.assert_any_call(
        QolsysNotification.PARTITION_UPDATE, entity._handle_update
    )


async def test_zone_entity_register_unregister(controller: MagicMock) -> None:
    """The zone entity subscribes/unsubscribes to zone updates."""
    entity = QolsysZoneEntity(controller, "1", UID)

    await entity.async_added_to_hass()
    cast(MagicMock, entity._zone).register.assert_any_call(
        QolsysNotification.ZONE_UPDATE, entity._handle_update
    )

    await entity.async_will_remove_from_hass()
    cast(MagicMock, entity._zone).unregister.assert_any_call(
        QolsysNotification.ZONE_UPDATE, entity._handle_update
    )


async def test_panel_sensor_entity_register_unregister(controller: MagicMock) -> None:
    """The panel-sensor entity subscribes/unsubscribes to settings updates."""
    entity = QolsysPanelSensorEntity(controller, "AC_STATUS", UID)

    await entity.async_added_to_hass()
    controller.state.register.assert_any_call(
        QolsysNotification.PANEL_SETTINGS_UPDATE, entity._handle_update
    )

    await entity.async_will_remove_from_hass()
    controller.state.unregister.assert_any_call(
        QolsysNotification.PANEL_SETTINGS_UPDATE, entity._handle_update
    )


async def test_weather_entity_register_unregister(controller: MagicMock) -> None:
    """The weather entity subscribes/unsubscribes to weather updates."""
    entity = QolsysWeatherEntity(controller, UID)

    await entity.async_added_to_hass()
    controller.state.weather.register.assert_any_call(
        QolsysNotification.WEATHER_UPDATE, entity._handle_update
    )

    await entity.async_will_remove_from_hass()
    controller.state.weather.unregister.assert_any_call(
        QolsysNotification.WEATHER_UPDATE, entity._handle_update
    )


async def test_automation_device_register_unregister(controller: MagicMock) -> None:
    """The automation-device entity subscribes/unsubscribes to updates."""
    entity = QolsysAutomationDeviceEntity(controller, "5", UID)

    await entity.async_added_to_hass()
    cast(MagicMock, entity._autdev).register.assert_any_call(
        QolsysNotification.AUTOMATION_UPDATE, entity._handle_update
    )

    await entity.async_will_remove_from_hass()
    cast(MagicMock, entity._autdev).unregister.assert_any_call(
        QolsysNotification.AUTOMATION_UPDATE, entity._handle_update
    )


def test_automation_device_available_malfunction(controller: MagicMock) -> None:
    """A malfunctioning status service makes the device unavailable."""
    entity = QolsysAutomationDeviceEntity(controller, "5", UID)
    cast(MagicMock, entity._autdev).service_get_protocol.return_value = [
        MagicMock(is_malfunctioning=True)
    ]
    assert entity.available is False


@pytest.mark.parametrize(
    ("state", "expected"),
    [(ControllerState.CONNECTED, True), (ControllerState.RECONNECTING, False)],
)
def test_automation_device_available_connected(
    controller: MagicMock, state: ControllerState, expected: bool
) -> None:
    """With no malfunction, availability follows the controller state."""
    entity = QolsysAutomationDeviceEntity(controller, "5", UID)
    cast(MagicMock, entity._autdev).service_get_protocol.return_value = [
        MagicMock(is_malfunctioning=False)
    ]
    controller.controller_state = state
    assert entity.available is expected


def test_automation_device_missing_raises(controller: MagicMock) -> None:
    """A missing automation device raises a clear error."""
    controller.state.automation_device.return_value = None
    with pytest.raises(ValueError, match="virtual_node_id"):
        QolsysAutomationDeviceEntity(controller, "5", UID)


def test_handle_update_writes_state_without_force_refresh(
    controller: MagicMock,
) -> None:
    """The observer callback writes the state directly (audit M4).

    The library calls the observer with an Event when the callback takes a
    positional argument; schedule_update_ha_state read that Event as
    force_refresh=True and sent HA down the create-a-Task path for an update
    method these entities do not define.
    """
    entity = QolsysPanelEntity(controller, UID)
    entity.async_write_ha_state = MagicMock()
    entity.schedule_update_ha_state = MagicMock()

    entity._handle_update(Event(QolsysNotification.PANEL_STATUS_UPDATE, controller))
    entity._handle_update()

    assert entity.async_write_ha_state.call_count == 2
    entity.schedule_update_ha_state.assert_not_called()


def test_handle_update_writes_directly_on_the_loop_thread(controller: MagicMock) -> None:
    """On the event-loop thread the state is written straight away."""
    entity = QolsysPartitionEntity(controller, "1", UID)
    entity.hass = MagicMock(loop_thread_id=threading.get_ident())
    entity.async_write_ha_state = MagicMock()

    entity._handle_update(None)

    entity.async_write_ha_state.assert_called_once_with()
    entity.hass.loop.call_soon_threadsafe.assert_not_called()


def test_handle_update_marshals_to_the_loop_from_another_thread(
    controller: MagicMock,
) -> None:
    """Off the loop (the library notifying from an executor) the write is handed to the loop."""
    entity = QolsysPartitionEntity(controller, "1", UID)
    entity.hass = MagicMock(loop_thread_id=threading.get_ident())
    entity.async_write_ha_state = MagicMock()

    worker = threading.Thread(target=entity._handle_update)
    worker.start()
    worker.join()

    entity.async_write_ha_state.assert_not_called()
    entity.hass.loop.call_soon_threadsafe.assert_called_once_with(
        entity.async_write_ha_state
    )


def test_handle_update_without_hass_writes_directly(controller: MagicMock) -> None:
    """With no hass there is no loop to marshal to; the write goes straight through."""
    entity = QolsysPartitionEntity(controller, "1", UID)
    entity.async_write_ha_state = MagicMock()

    entity._handle_update(None)

    entity.async_write_ha_state.assert_called_once_with()


# The via_device_id link (1.7.2/1.7.3). The cases are upstream df56d60's, adapted
# to this fork's resolver: a missing parent leaves the child unlinked rather than
# falling back to the deprecated `via_device` tuple, which is what HA 2026.9
# raised on when an entity was re-added from the settings UI.


def test_device_info_links_child_to_panel_by_registry_id(
    controller: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A child device carries the panel's registry id as via_device_id."""
    registry = MagicMock()
    registry.async_get_device_by_identifier.return_value = MagicMock(id="dev-123")
    monkeypatch.setattr(entity_module.dr, "async_get", lambda hass: registry)

    entity = QolsysZoneEntity(controller, "1", UID)
    entity.hass = MagicMock()
    entity.platform = MagicMock()
    entity.platform.config_entry.entry_id = "entry-1"

    info = entity.device_info
    assert info is not None
    data = dict(info)
    assert data["via_device_id"] == "dev-123"
    assert "via_device" not in data
    assert data["identifiers"] == {(DOMAIN, f"{UID}_zone1")}
    registry.async_get_device_by_identifier.assert_called_once_with(
        (DOMAIN, UID), "entry-1"
    )


def test_device_info_parent_missing_leaves_child_unlinked(
    controller: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no panel device in the registry the child gets neither via key."""
    registry = MagicMock()
    registry.async_get_device_by_identifier.return_value = None
    monkeypatch.setattr(entity_module.dr, "async_get", lambda hass: registry)

    entity = QolsysZoneEntity(controller, "1", UID)
    entity.hass = MagicMock()
    entity.platform = MagicMock()
    entity.platform.config_entry.entry_id = "entry-1"

    info = entity.device_info
    assert info is not None
    data = dict(info)
    assert "via_device" not in data
    assert "via_device_id" not in data


def test_device_info_before_hass_is_set_has_no_link(controller: MagicMock) -> None:
    """Before the entity is added to hass there is no registry to resolve against."""
    entity = QolsysPartitionEntity(controller, "1", UID)

    info = entity.device_info
    assert info is not None
    data = dict(info)
    assert "via_device" not in data
    assert "via_device_id" not in data


def test_device_info_panel_entity_has_no_parent_link(
    controller: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The panel's own entities are the parent; no lookup, no via key."""
    registry = MagicMock()
    monkeypatch.setattr(entity_module.dr, "async_get", lambda hass: registry)

    entity = QolsysPanelEntity(controller, UID)
    entity.hass = MagicMock()
    entity.platform = MagicMock()

    info = entity.device_info
    assert info is not None
    data = dict(info)
    assert "via_device" not in data
    assert "via_device_id" not in data
    registry.async_get_device_by_identifier.assert_not_called()
