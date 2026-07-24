"""Tests for the Qolsys Panel base entities."""

from typing import cast
from unittest.mock import MagicMock

from conftest import PANEL_MAC
import pytest
from qolsys_controller.enum_qolsys import ControllerState, QolsysNotification

from custom_components.qolsys_panel.entity import (
    QolsysAutomationDeviceEntity,
    QolsysPanelEntity,
    QolsysPanelSensorEntity,
    QolsysPartitionEntity,
    QolsysWeatherEntity,
    QolsysZoneEntity,
)

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
        QolsysNotification.PANEL_STATUS_UPDATE, entity.schedule_update_ha_state
    )

    await entity.async_will_remove_from_hass()
    controller.state.unregister.assert_any_call(
        QolsysNotification.PANEL_STATUS_UPDATE, entity.schedule_update_ha_state
    )


async def test_partition_entity_register_unregister(controller: MagicMock) -> None:
    """The partition entity subscribes/unsubscribes to partition updates."""
    entity = QolsysPartitionEntity(controller, "1", UID)

    await entity.async_added_to_hass()
    cast(MagicMock, entity._partition).register.assert_any_call(
        QolsysNotification.PARTITION_UPDATE, entity.schedule_update_ha_state
    )

    await entity.async_will_remove_from_hass()
    cast(MagicMock, entity._partition).unregister.assert_any_call(
        QolsysNotification.PARTITION_UPDATE, entity.schedule_update_ha_state
    )


async def test_zone_entity_register_unregister(controller: MagicMock) -> None:
    """The zone entity subscribes/unsubscribes to zone updates."""
    entity = QolsysZoneEntity(controller, "1", UID)

    await entity.async_added_to_hass()
    cast(MagicMock, entity._zone).register.assert_any_call(
        QolsysNotification.ZONE_UPDATE, entity.schedule_update_ha_state
    )

    await entity.async_will_remove_from_hass()
    cast(MagicMock, entity._zone).unregister.assert_any_call(
        QolsysNotification.ZONE_UPDATE, entity.schedule_update_ha_state
    )


async def test_panel_sensor_entity_register_unregister(controller: MagicMock) -> None:
    """The panel-sensor entity subscribes/unsubscribes to settings updates."""
    entity = QolsysPanelSensorEntity(controller, "AC_STATUS", UID)

    await entity.async_added_to_hass()
    controller.state.register.assert_any_call(
        QolsysNotification.PANEL_SETTINGS_UPDATE, entity.schedule_update_ha_state
    )

    await entity.async_will_remove_from_hass()
    controller.state.unregister.assert_any_call(
        QolsysNotification.PANEL_SETTINGS_UPDATE, entity.schedule_update_ha_state
    )


async def test_weather_entity_register_unregister(controller: MagicMock) -> None:
    """The weather entity subscribes/unsubscribes to weather updates."""
    entity = QolsysWeatherEntity(controller, UID)

    await entity.async_added_to_hass()
    controller.state.weather.register.assert_any_call(
        QolsysNotification.WEATHER_UPDATE, entity.schedule_update_ha_state
    )

    await entity.async_will_remove_from_hass()
    controller.state.weather.unregister.assert_any_call(
        QolsysNotification.WEATHER_UPDATE, entity.schedule_update_ha_state
    )


async def test_automation_device_register_unregister(controller: MagicMock) -> None:
    """The automation-device entity subscribes/unsubscribes to updates."""
    entity = QolsysAutomationDeviceEntity(controller, "5", UID)

    await entity.async_added_to_hass()
    cast(MagicMock, entity._autdev).register.assert_any_call(
        QolsysNotification.AUTOMATION_UPDATE, entity.schedule_update_ha_state
    )

    await entity.async_will_remove_from_hass()
    cast(MagicMock, entity._autdev).unregister.assert_any_call(
        QolsysNotification.AUTOMATION_UPDATE, entity.schedule_update_ha_state
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
