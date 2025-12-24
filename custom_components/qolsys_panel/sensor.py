"""Sensor platform for Qolsys Panel."""

from __future__ import annotations

from qolsys_controller import qolsys_controller

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import QolsysPanelConfigEntry
from .entity import (
    QolsysZoneEntity,
    QolsysZwaveDimmerEntity,
    QolsysZwaveLockEntity,
    QolsysZwavePowerMeterEntity,
    QolsysZwaveThermometerEntity,
    QolsysZwaveThermostatEntity,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    QolsysPanel = config_entry.runtime_data

    entities: list[SensorEntity] = []

    # Add Zone Sensors
    for zone in QolsysPanel.state.zones:
        if zone.is_latest_dbm_enabled():
            entities.append(
                ZoneSensor_LatestDBM(QolsysPanel, zone.zone_id, config_entry.unique_id)
            )

        if zone.is_average_dbm_enabled():
            entities.append(
                ZoneSensor_AverageDBM(QolsysPanel, zone.zone_id, config_entry.unique_id)
            )

        # Add PowerG Sensors if enabled
        if zone.is_powerg_temperature_enabled():
            entities.append(
                ZoneSensor_PowerG_Temperature(
                    QolsysPanel, zone.zone_id, config_entry.unique_id
                )
            )

        # Add PowerG Light Sensor if enabled
        if zone.is_powerg_light_enabled():
            entities.append(
                ZoneSensor_PowerG_Light(
                    QolsysPanel, zone.zone_id, config_entry.unique_id
                )
            )

    # Add Z-Wave Dimmer Sensors
    for dimmer in QolsysPanel.state.zwave_dimmers:
        # Add Battery Value if battery present
        if dimmer.is_battery_enabled():
            entities.append(
                DimmerSensor_BatteryValue(
                    QolsysPanel, dimmer.node_id, config_entry.unique_id
                )
            )

    # Add Z-Wave Lock Sensors
    for lock in QolsysPanel.state.zwave_locks:
        if lock.is_battery_enabled():
            entities.append(
                LockSensor_BatteryValue(
                    QolsysPanel, lock.node_id, config_entry.unique_id
                )
            )

    # Add Z-Wave Thermostat Sensors
    for thermostat in QolsysPanel.state.zwave_thermostats:
        if thermostat.is_battery_enabled():
            entities.append(
                ThermostatSensor_BatteryValue(
                    QolsysPanel, thermostat.node_id, config_entry.unique_id
                )
            )

    # Add Z-Wave Thermometer Sensors
    for thermometer in QolsysPanel.state.zwave_thermometer:
        entities.append(
            ThermometerSensor_Value(
                QolsysPanel, thermometer.node_id, config_entry.unique_id
            )
        )

        if thermometer.is_battery_enabled():
            entities.append(
                ThermometerSensor_BatteryValue(
                    QolsysPanel, thermometer.node_id, config_entry.unique_id
                )
            )

    # Add Z-Wave Power Meter Sensors

    async_add_entities(entities)


class ZoneSensor_LatestDBM(QolsysZoneEntity, SensorEntity):
    """A sensor entity for a zone latest DBM."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, QolsysPanel: qolsys_controller, zone_id: int, unique_id: str
    ) -> None:
        """Set up a binary sensor entity for a zone battery status."""
        super().__init__(QolsysPanel, zone_id, unique_id)
        self._attr_unique_id = f"{self._zone_unique_id}_latestdBm"
        self._attr_translation_key = "latest_dbm"
        self._attr_native_unit_of_measurement = "dBm"
        self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return the latest dBm value of the zone."""
        return self._zone.latestdBm


class ZoneSensor_AverageDBM(QolsysZoneEntity, SensorEntity):
    """A sensor entity for the average DBM of a zone."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, QolsysPanel: qolsys_controller, zone_id: int, unique_id: str
    ) -> None:
        """Set up a binary sensor entity for a zone battery status."""
        super().__init__(QolsysPanel, zone_id, unique_id)
        self._attr_unique_id = f"{self._zone_unique_id}_averagedBm"
        self._attr_translation_key = "average_dbm"
        self._attr_native_unit_of_measurement = "dBm"
        self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return the latest dBm value of the zone."""
        return self._zone.averagedBm


class ZoneSensor_PowerG_Temperature(QolsysZoneEntity, SensorEntity):
    """A sensor entity for PowerG Temperature."""

    def __init__(
        self, QolsysPanel: qolsys_controller, zone_id: int, unique_id: str
    ) -> None:
        """Set up a binary sensor entity for a zone powerg temperature."""
        super().__init__(QolsysPanel, zone_id, unique_id)
        self._attr_unique_id = f"{self._zone_unique_id}_powerg_temperature"
        self._attr_translation_key = "powerg_temperature"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_suggested_display_precision = 1
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the latest Zone PowerG Temperature."""
        return self._zone.powerg_temperature


class ZoneSensor_PowerG_Light(QolsysZoneEntity, SensorEntity):
    """A sensor entity for PowerG Light."""

    def __init__(
        self, QolsysPanel: qolsys_controller, zone_id: int, unique_id: str
    ) -> None:
        """Set up a binary sensor entity for a zone powerg light."""
        super().__init__(QolsysPanel, zone_id, unique_id)
        self._attr_unique_id = f"{self._zone_unique_id}_powerg_light"
        self._attr_translation_key = "powerg_light"
        self._attr_native_unit_of_measurement = "lx"
        self._attr_device_class = SensorDeviceClass.ILLUMINANCE
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the latest Zone PowerG Light."""
        return self._zone.powerg_light


class DimmerSensor_BatteryValue(QolsysZwaveDimmerEntity, SensorEntity):
    """A sensor entity for a dimmer battery value."""

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: int, unique_id: str
    ) -> None:
        """Set up a sensor entity for a dimmer battery value."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = f"{self._zwave_dimmer_unique_id}_battery_value"
        self._attr_translation_key = "dimmer_battery"
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return dimmer battery value."""
        return self._dimmer.node_battery_level_value


class LockSensor_BatteryValue(QolsysZwaveLockEntity, SensorEntity):
    """A sensor entity for a lock battery value."""

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: int, unique_id: str
    ) -> None:
        """Set up a sensor entity for a lock battery value."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = f"{self._zwave_lock_unique_id}_battery_value"
        self._attr_translation_key = "lock_battery"
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return lock battery value."""
        return self._lock.node_battery_level_value


class ThermostatSensor_BatteryValue(QolsysZwaveThermostatEntity, SensorEntity):
    """A sensor entity for a thermostat battery value."""

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: int, unique_id: str
    ) -> None:
        """Set up a sensor entity for a thermostat battery value."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = f"{self._zwave_thermostat_unique_id}_battery_value"
        self._attr_translation_key = "thermostat_battery"
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return thermostat battery value."""
        return self._thermostat.node_battery_level_value


class ThermometerSensor_Value(QolsysZwaveThermometerEntity, SensorEntity):
    """A sensor entity for a thermometer value."""

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: int, unique_id: str
    ) -> None:
        """Set up a sensor entity for a thermometer value."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = self._zwave_thermometer_unique_id
        self._attr_translation_key = "temperature"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return thermometer value."""
        return 99


class ThermometerSensor_BatteryValue(QolsysZwaveThermometerEntity, SensorEntity):
    """A sensor entity for a thermometer battery value."""

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: int, unique_id: str
    ) -> None:
        """Set up a sensor entity for a thermometer battery value."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = f"{self._zwave_thermometer_unique_id}_battery_value"
        self._attr_translation_key = "thermometer_battery"
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return thermometer battery value."""
        return self._thermometer.node_battery_level_value


class PowerMeterSensor_Value(QolsysZwavePowerMeterEntity, SensorEntity):
    """A sensor entity for a power meter value."""

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: int, unique_id: str
    ) -> None:
        """Set up a sensor entity for a power meter value."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = self._zwave_powermeter_unique_id
        self._attr_translation_key = "power"
        self._attr_native_unit_of_measurement = "kW"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return powermeter value."""
        return 9999


class PowerMeterSensor_BatteryValue(QolsysZwavePowerMeterEntity, SensorEntity):
    """A sensor entity for a power meter battery value."""

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: int, unique_id: str
    ) -> None:
        """Set up a sensor entity for a power meter battery value."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = f"{self._zwave_powermeter_unique_id}_battery_value"
        self._attr_translation_key = "powermeter_battery"
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return power meter battery value."""
        return self._powermeter.node_battery_level_value
