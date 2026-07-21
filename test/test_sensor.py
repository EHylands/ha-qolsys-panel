"""Tests for the Qolsys Panel sensors."""

from unittest.mock import MagicMock

from conftest import PANEL_MAC
import pytest
from qolsys_controller.automation.service_battery import BatteryService
from qolsys_controller.automation.service_meter import MeterService
from qolsys_controller.automation.service_sensor import SensorService
from qolsys_controller.enum_qolsys import (
    PartitionError,
    QolsysMeterScale,
    QolsysNotification,
    QolsysSensorScale,
)

from custom_components.qolsys_panel.sensor import (
    AutomationDevice_BatteryValue,
    AutomationDevice_Meter,
    AutomationDevice_Sensor,
    Partition_LastError,
    ZoneSensor_AverageDBM,
    ZoneSensor_BatteryLevel,
    ZoneSensor_BatteryVoltage,
    ZoneSensor_LatestDBM,
    ZoneSensor_PowerG_Light,
    ZoneSensor_PowerG_Temperature,
    async_setup_entry,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant

UID = PANEL_MAC

ZONE_SENSORS = [
    (ZoneSensor_LatestDBM, "latestdBm"),
    (ZoneSensor_AverageDBM, "averagedBm"),
    (ZoneSensor_PowerG_Temperature, "powerg_temperature"),
    (ZoneSensor_PowerG_Light, "powerg_light"),
    (ZoneSensor_BatteryLevel, "powerg_battery_level"),
    (ZoneSensor_BatteryVoltage, "powerg_battery_voltage"),
]

METER_DEVICE_CLASSES = [
    (QolsysMeterScale.KWH, SensorDeviceClass.ENERGY),
    (QolsysMeterScale.KVAH, SensorDeviceClass.ENERGY),
    (QolsysMeterScale.WATTS, SensorDeviceClass.POWER),
    (QolsysMeterScale.PULSE_COUNT, SensorDeviceClass.FREQUENCY),
    (QolsysMeterScale.VOLTS, SensorDeviceClass.VOLTAGE),
    (QolsysMeterScale.AMPS, SensorDeviceClass.CURRENT),
    (QolsysMeterScale.POWER_FACTOR, SensorDeviceClass.POWER_FACTOR),
    (QolsysMeterScale.KVAR, SensorDeviceClass.REACTIVE_POWER),
    (QolsysMeterScale.KVARH, SensorDeviceClass.REACTIVE_POWER),
    (QolsysMeterScale.CUBIC_METERS, SensorDeviceClass.VOLUME),
    (QolsysMeterScale.CUBIC_FEET, SensorDeviceClass.VOLUME),
    (QolsysMeterScale.US_GALLONS, SensorDeviceClass.VOLUME),
    (QolsysMeterScale.UNKNOWN, None),
]

METER_STATE_CLASSES = [
    (QolsysMeterScale.KWH, SensorStateClass.TOTAL_INCREASING),
    (QolsysMeterScale.KVAH, SensorStateClass.TOTAL),
    (QolsysMeterScale.WATTS, SensorStateClass.MEASUREMENT),
    (QolsysMeterScale.PULSE_COUNT, SensorStateClass.TOTAL),
    (QolsysMeterScale.VOLTS, SensorStateClass.MEASUREMENT),
    (QolsysMeterScale.AMPS, SensorStateClass.MEASUREMENT),
    (QolsysMeterScale.POWER_FACTOR, SensorStateClass.MEASUREMENT),
    (QolsysMeterScale.KVAR, SensorStateClass.MEASUREMENT),
    (QolsysMeterScale.KVARH, SensorStateClass.TOTAL),
    (QolsysMeterScale.CUBIC_METERS, SensorStateClass.TOTAL_INCREASING),
    (QolsysMeterScale.CUBIC_FEET, SensorStateClass.TOTAL_INCREASING),
    (QolsysMeterScale.US_GALLONS, SensorStateClass.TOTAL_INCREASING),
    (QolsysMeterScale.UNKNOWN, SensorStateClass.TOTAL),
]


@pytest.fixture
def controller() -> MagicMock:
    """A controller mock with a partition, a zone and an automation device."""
    c = MagicMock()

    partition = MagicMock()
    partition.id = "1"
    c.state.partitions = [partition]

    zone = MagicMock()
    zone.zone_id = "1"
    for flag in (
        "is_latest_dbm_enabled",
        "is_average_dbm_enabled",
        "is_powerg_temperature_enabled",
        "is_powerg_light_enabled",
        "is_powerg_battery_level_enabled",
        "is_powerg_battery_voltage_enabled",
    ):
        getattr(zone, flag).return_value = True
    c.state.zones = [zone]

    battery_service = MagicMock()
    battery_service.endpoint = 0
    battery_service.supports_battery_level.return_value = True

    sensor_obj = MagicMock()
    sensor_obj.unit = QolsysSensorScale.TEMPERATURE_FAHRENHEIT
    sensor_service = MagicMock()
    sensor_service.endpoint = 0
    sensor_service.sensors = [sensor_obj]

    meter_obj = MagicMock()
    meter_obj.unit = QolsysMeterScale.KWH
    meter_service = MagicMock()
    meter_service.endpoint = 0
    meter_service.meters = [meter_obj]

    device = MagicMock()
    device.virtual_node_id = "5"
    device.service_get_protocol.side_effect = lambda proto: {
        BatteryService: [battery_service],
        SensorService: [sensor_service],
        MeterService: [meter_service],
    }.get(proto, [])
    c.state.automation_devices = [device]

    return c


async def test_async_setup_entry_creates_entities(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup builds partition, zone and automation-device sensors."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    # 1 partition + 6 zone + 3 automation (battery, sensor, meter)
    assert len(entities) == 10
    assert {
        "Partition_LastError",
        "ZoneSensor_LatestDBM",
        "AutomationDevice_BatteryValue",
        "AutomationDevice_Sensor",
        "AutomationDevice_Meter",
    } <= {type(e).__name__ for e in entities}


async def test_dynamic_sensor_add(hass: HomeAssistant, controller: MagicMock) -> None:
    """A dynamic sensor-add notification adds a new sensor entity."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    callback = next(
        call.args[1]
        for call in controller.state.register.call_args_list
        if call.args[0] is QolsysNotification.AUTOMATION_SENSOR_ADD
    )
    await callback(
        virtual_node_id="5",
        endpoint=0,
        unit=QolsysSensorScale.TEMPERATURE_FAHRENHEIT,
    )

    assert add_entities.call_count == 2


@pytest.mark.parametrize(("sensor_cls", "attr"), ZONE_SENSORS)
def test_zone_sensor_native_value(controller: MagicMock, sensor_cls, attr) -> None:
    """Each zone sensor returns its backing zone attribute."""
    sensor = sensor_cls(controller, "1", UID)
    setattr(sensor._zone, attr, 42)
    assert sensor.native_value == 42


def test_automation_battery_value(controller: MagicMock) -> None:
    """The automation battery sensor returns the service battery level."""
    sensor = AutomationDevice_BatteryValue(controller, "5", 0, UID)
    sensor._service.battery_level = 88
    assert sensor.native_value == 88


@pytest.mark.parametrize(
    ("unit", "unit_str", "device_class"),
    [
        (QolsysSensorScale.TEMPERATURE_FAHRENHEIT, "°F", SensorDeviceClass.TEMPERATURE),
        (QolsysSensorScale.TEMPERATURE_CELSIUS, "°C", SensorDeviceClass.TEMPERATURE),
        (QolsysSensorScale.RELATIVE_HUMIDITY, "%", SensorDeviceClass.HUMIDITY),
        (QolsysSensorScale.WIND_DIRECTION, None, None),
    ],
)
def test_automation_sensor_unit_and_class(
    controller: MagicMock, unit, unit_str, device_class
) -> None:
    """The automation sensor maps its scale to a unit and device class."""
    sensor = AutomationDevice_Sensor(controller, "5", 0, unit, UID)
    assert sensor.native_unit_of_measurement == unit_str
    assert sensor.device_class == device_class


def test_automation_sensor_native_value(controller: MagicMock) -> None:
    """The automation sensor returns its backing sensor value."""
    sensor = AutomationDevice_Sensor(
        controller, "5", 0, QolsysSensorScale.TEMPERATURE_FAHRENHEIT, UID
    )
    sensor._sensor.value = 21.5
    assert sensor.native_value == 21.5


def test_automation_meter_native_unit(controller: MagicMock) -> None:
    """The automation meter reports its scale's unit string."""
    meter = AutomationDevice_Meter(controller, "5", 0, QolsysMeterScale.KWH, UID)
    assert meter.native_unit_of_measurement == "kWh"


@pytest.mark.parametrize(("unit", "device_class"), METER_DEVICE_CLASSES)
def test_automation_meter_device_class(
    controller: MagicMock, unit, device_class
) -> None:
    """The automation meter maps its scale to a device class."""
    meter = AutomationDevice_Meter(controller, "5", 0, unit, UID)
    assert meter.device_class == device_class


@pytest.mark.parametrize(("unit", "state_class"), METER_STATE_CLASSES)
def test_automation_meter_state_class(controller: MagicMock, unit, state_class) -> None:
    """The automation meter maps its scale to a state class."""
    meter = AutomationDevice_Meter(controller, "5", 0, unit, UID)
    assert meter.state_class == state_class


def test_automation_meter_native_value(controller: MagicMock) -> None:
    """The automation meter returns its backing meter value."""
    meter = AutomationDevice_Meter(controller, "5", 0, QolsysMeterScale.KWH, UID)
    meter._meter.value = 12.34
    assert meter.native_value == 12.34


def test_partition_last_error(controller: MagicMock) -> None:
    """The partition last-error sensor exposes the error name and options."""
    sensor = Partition_LastError(controller, "1", UID)
    sensor._partition.last_error = PartitionError.USER_CODE_ERROR
    assert sensor.native_value == "USER_CODE_ERROR"
    assert sensor._attr_options == [error.name for error in PartitionError]
