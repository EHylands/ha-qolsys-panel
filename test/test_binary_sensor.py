"""Tests for the Qolsys Panel binary sensors."""

from unittest.mock import MagicMock, patch

from conftest import PANEL_MAC
import pytest
from qolsys_controller.enum_qolsys import (
    PartitionAlarmType,
    PartitionQuickExitState,
    ZoneSensorType,
    ZoneStatus,
)

from custom_components.qolsys_panel.binary_sensor import (
    PANEL_SENSOR,
    AutomationDevice_Status,
    PanelSensor,
    PartitionAlarmSensor,
    PartitionEntryDelaySensor,
    PartitionExitSoundSensor,
    PartitionQuickExitSensor,
    QolsysChimeSensor,
    QolsysDoorbellSensor,
    ZoneSensor_ACStatus,
    ZoneSensor_BatteryStatus,
    ZoneSensor_Tamper,
    ZoneSensor_Unreachable,
    ZonesSensor,
    async_setup_entry,
)
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant

UID = PANEL_MAC
CALL_LATER = "custom_components.qolsys_panel.binary_sensor.async_call_later"


@pytest.fixture
def controller() -> MagicMock:
    """A controller mock exposing one zone, partition and automation device."""
    c = MagicMock()

    zone = MagicMock()
    zone.zone_id = "1"
    zone.is_battery_enabled.return_value = True
    zone.is_powerg_battery_level_enabled.return_value = False
    zone.is_ac_enabled.return_value = True
    c.state.zones = [zone]

    partition = MagicMock()
    partition.id = "1"
    c.state.partitions = [partition]

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
    """Setup builds the full set of binary sensors from controller state."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    # 2 (doorbell+chime) + 5 (zone) + 10 (panel) + 7 (partition) + 1 (autdev)
    assert len(entities) == 25
    types = {type(e).__name__ for e in entities}
    assert {
        "QolsysDoorbellSensor",
        "QolsysChimeSensor",
        "ZonesSensor",
        "PanelSensor",
        "PartitionAlarmSensor",
        "AutomationDevice_Status",
    } <= types


def test_partition_exit_sound(controller: MagicMock) -> None:
    """Exit-sound sensor reflects the partition flag."""
    sensor = PartitionExitSoundSensor(controller, "1", UID)
    sensor._partition.exit_sounds = True
    assert sensor.is_on is True
    sensor._partition.exit_sounds = False
    assert sensor.is_on is False


def test_partition_entry_delay(controller: MagicMock) -> None:
    """Entry-delay sensor reflects the partition flag."""
    sensor = PartitionEntryDelaySensor(controller, "1", UID)
    sensor._partition.entry_delays = True
    assert sensor.is_on is True
    sensor._partition.entry_delays = False
    assert sensor.is_on is False


def test_partition_quick_exit(controller: MagicMock) -> None:
    """Quick-exit sensor is on only while a quick exit window is active."""
    sensor = PartitionQuickExitSensor(controller, "1", UID)
    sensor._partition.quick_exit_state = PartitionQuickExitState.STARTED
    assert sensor.is_on is True
    sensor._partition.quick_exit_state = PartitionQuickExitState.COMPLETED
    assert sensor.is_on is False

    attrs = sensor.extra_state_attributes
    assert set(attrs) == {"quick_exit_state", "delay", "start_time"}


@pytest.mark.parametrize(
    ("alarm_type", "present"),
    [
        ("Police", PartitionAlarmType.POLICE_EMERGENCY),
        ("Police", PartitionAlarmType.SILENT_POLICE_EMERGENCY),
        ("Fire", PartitionAlarmType.FIRE_EMERGENCY),
        ("Auxiliary", PartitionAlarmType.AUXILIARY_EMERGENCY),
        ("Auxiliary", PartitionAlarmType.SILENT_AUXILIARY_EMERGENCY),
        ("Gaz", PartitionAlarmType.GAZ_CO),
    ],
)
def test_partition_alarm_sensor(
    controller: MagicMock, alarm_type: str, present: PartitionAlarmType
) -> None:
    """Each alarm sensor is on when its alarm type is active on the partition."""
    sensor = PartitionAlarmSensor(controller, "1", UID, alarm_type)
    sensor._partition.alarm_type_array = [present]
    assert sensor.is_on is True
    sensor._partition.alarm_type_array = []
    assert sensor.is_on is False


@pytest.mark.parametrize(
    ("key", "attr", "on_value", "off_value"),
    [
        ("AC_STATUS", "AC_STATUS", "ON", "OFF"),
        ("PANEL_TAMPER_STATE", "PANEL_TAMPER_STATE", "1", "0"),
        ("BATTERY_STATUS", "BATTERY_STATUS", "LOW", "OKAY"),
        ("FAIL_TO_COMMUNICATE", "FAIL_TO_COMMUNICATE", "false", "true"),
        ("ZWAVE_CONTROLLER", "ZWAVE_CONTROLLER", "true", "false"),
        ("SECURE_ARMING", "SECURE_ARMING", "true", "false"),
        ("AUTO_STAY", "AUTO_STAY", "true", "false"),
        ("AUTO_ARM_STAY", "AUTO_ARM_STAY", "true", "false"),
        ("CONTROL_4", "CONTROL_4", "true", "false"),
        ("AUTO_BYPASS", "AUTO_BYPASS", "true", "false"),
    ],
)
def test_panel_sensor(
    controller: MagicMock, key: str, attr: str, on_value: str, off_value: str
) -> None:
    """Each panel diagnostic sensor maps its panel attribute to on/off."""
    description = next(d for d in PANEL_SENSOR if d.key == key)
    sensor = PanelSensor(controller, UID, description)

    setattr(controller.panel, attr, on_value)
    assert sensor.is_on is True
    setattr(controller.panel, attr, off_value)
    assert sensor.is_on is False


def test_panel_sensor_unknown_key(controller: MagicMock) -> None:
    """An unrecognised panel sensor key is always off."""
    description = BinarySensorEntityDescription(key="UNKNOWN")
    sensor = PanelSensor(controller, UID, description)
    assert sensor.is_on is False


def test_zone_unreachable(controller: MagicMock) -> None:
    """Connectivity sensor is on unless the zone is unreachable."""
    sensor = ZoneSensor_Unreachable(controller, "1", UID)
    sensor._zone.sensorstatus = "Closed"
    assert sensor.is_on is True
    sensor._zone.sensorstatus = "Unreachable"
    assert sensor.is_on is False


def test_zone_tamper(controller: MagicMock) -> None:
    """Tamper sensor is on when the zone reports tampered."""
    sensor = ZoneSensor_Tamper(controller, "1", UID)
    sensor._zone.sensorstatus = ZoneStatus.TAMPERED
    assert sensor.is_on is True
    sensor._zone.sensorstatus = ZoneStatus.CLOSED
    assert sensor.is_on is False


def test_zone_battery_status(controller: MagicMock) -> None:
    """Battery sensor is on when battery status is not normal."""
    sensor = ZoneSensor_BatteryStatus(controller, "1", UID)
    sensor._zone.battery_status = "Low"
    assert sensor.is_on is True
    sensor._zone.battery_status = "Normal"
    assert sensor.is_on is False


def test_zone_ac_status(controller: MagicMock) -> None:
    """AC sensor is on when the zone AC status is normal."""
    sensor = ZoneSensor_ACStatus(controller, "1", UID)
    sensor._zone.ac_status = "Normal"
    assert sensor.is_on is True
    sensor._zone.ac_status = "Fault"
    assert sensor.is_on is False


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ZoneStatus.OPEN, True),
        (ZoneStatus.ALARMED, True),
        (ZoneStatus.CLOSED, False),
    ],
)
def test_zones_sensor_is_on(
    controller: MagicMock, status: ZoneStatus, expected: bool
) -> None:
    """The main zone sensor is on for open/active states."""
    sensor = ZonesSensor(controller, "1", UID)
    sensor._zone.sensorstatus = status
    assert sensor.is_on is expected


@pytest.mark.parametrize(
    ("sensortype", "expected"),
    [
        (ZoneSensorType.PANEL_MOTION, BinarySensorDeviceClass.MOTION),
        (ZoneSensorType.MOTION, BinarySensorDeviceClass.MOTION),
        (ZoneSensorType.DOOR_WINDOW, BinarySensorDeviceClass.DOOR),
        (ZoneSensorType.PANEL_GLASS_BREAK, BinarySensorDeviceClass.PROBLEM),
        (ZoneSensorType.GLASS_BREAK, BinarySensorDeviceClass.PROBLEM),
        (ZoneSensorType.SMOKE_DETECTOR, BinarySensorDeviceClass.SMOKE),
        (ZoneSensorType.SMOKE_M, BinarySensorDeviceClass.SMOKE),
        (ZoneSensorType.CO_DETECTOR, BinarySensorDeviceClass.CO),
        (ZoneSensorType.AUXILIARY_PENDANT, BinarySensorDeviceClass.SAFETY),
        (ZoneSensorType.WATER, BinarySensorDeviceClass.MOISTURE),
        (ZoneSensorType.BLUETOOTH, None),
        (ZoneSensorType.KEYPAD, BinarySensorDeviceClass.PROBLEM),
        (ZoneSensorType.KEY_FOB, BinarySensorDeviceClass.SAFETY),
        (ZoneSensorType.TILT, BinarySensorDeviceClass.PROBLEM),
        (ZoneSensorType.FREEZE, BinarySensorDeviceClass.COLD),
        (ZoneSensorType.HEAT, BinarySensorDeviceClass.HEAT),
        (ZoneSensorType.DOORBELL, BinarySensorDeviceClass.PRESENCE),
        (ZoneSensorType.UNKNOWN, None),
    ],
)
def test_zones_sensor_device_class(
    controller: MagicMock, sensortype: ZoneSensorType, expected
) -> None:
    """The main zone sensor maps sensor type to a device class."""
    sensor = ZonesSensor(controller, "1", UID)
    sensor._zone.sensortype = sensortype
    assert sensor.device_class == expected


@pytest.mark.parametrize(("endpoint", "name"), [(0, "Node Status"), (2, None)])
def test_automation_device_status(
    controller: MagicMock, endpoint: int, name: str | None
) -> None:
    """Automation status sensor reflects the service malfunction flag."""
    sensor = AutomationDevice_Status(controller, "5", endpoint, UID)
    sensor._service.is_malfunctioning = True
    assert sensor.is_on is True
    sensor._service.is_malfunctioning = False
    assert sensor.is_on is False
    if name is not None:
        assert sensor._attr_name == name


def test_doorbell_press_turns_on(hass: HomeAssistant, controller: MagicMock) -> None:
    """A doorbell event turns the sensor on and schedules an auto-reset."""
    with patch(CALL_LATER, return_value=MagicMock()) as call_later:
        sensor = QolsysDoorbellSensor(hass, controller, UID)
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_doorbell_event({})

        assert sensor.is_on is True
        sensor.async_write_ha_state.assert_called_once()
        call_later.assert_called_once()


def test_doorbell_debounces_rapid_presses(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """A second press within the debounce window is ignored."""
    with patch(CALL_LATER, return_value=MagicMock()):
        sensor = QolsysDoorbellSensor(hass, controller, UID)
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_doorbell_event({})
        sensor._handle_doorbell_event({})

        assert sensor.async_write_ha_state.call_count == 1


def test_doorbell_cancels_previous_reset(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """A fresh press cancels the pending reset from the previous one."""
    with patch(CALL_LATER, return_value=MagicMock()):
        sensor = QolsysDoorbellSensor(hass, controller, UID)
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_doorbell_event({})
        first_cancel = sensor._cancel_reset
        sensor._last_press = 0.0  # bypass debounce
        sensor._handle_doorbell_event({})

        first_cancel.assert_called_once()


async def test_doorbell_reset(hass: HomeAssistant, controller: MagicMock) -> None:
    """The scheduled reset turns the sensor back off."""
    sensor = QolsysDoorbellSensor(hass, controller, UID)
    sensor.async_write_ha_state = MagicMock()
    sensor._attr_is_on = True

    await sensor._async_reset(None)

    assert sensor.is_on is False
    assert sensor._cancel_reset is None


def test_chime_press_turns_on(hass: HomeAssistant, controller: MagicMock) -> None:
    """A chime event turns the sensor on and schedules an auto-reset."""
    with patch(CALL_LATER, return_value=MagicMock()) as call_later:
        sensor = QolsysChimeSensor(hass, controller, UID)
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_chime_event({})

        assert sensor.is_on is True
        sensor.async_write_ha_state.assert_called_once()
        call_later.assert_called_once()


def test_chime_debounces_rapid_presses(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """A second chime within the debounce window is ignored."""
    with patch(CALL_LATER, return_value=MagicMock()):
        sensor = QolsysChimeSensor(hass, controller, UID)
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_chime_event({})
        sensor._handle_chime_event({})

        assert sensor.async_write_ha_state.call_count == 1


def test_chime_cancels_previous_reset(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """A fresh chime cancels the pending reset from the previous one."""
    with patch(CALL_LATER, return_value=MagicMock()):
        sensor = QolsysChimeSensor(hass, controller, UID)
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_chime_event({})
        first_cancel = sensor._cancel_reset
        sensor._last_press = 0.0  # bypass debounce
        sensor._handle_chime_event({})

        first_cancel.assert_called_once()


async def test_chime_reset(hass: HomeAssistant, controller: MagicMock) -> None:
    """The scheduled reset turns the chime sensor back off."""
    sensor = QolsysChimeSensor(hass, controller, UID)
    sensor.async_write_ha_state = MagicMock()
    sensor._attr_is_on = True

    await sensor._async_reset(None)

    assert sensor.is_on is False
    assert sensor._cancel_reset is None
