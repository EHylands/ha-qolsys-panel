"""Sensor platform for Qolsys Panel."""

from __future__ import annotations
from math import e

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
from .entity import QolsysZoneEntity, QolsysZwaveDimmerEntity, QolsysZwaveLockEntity, QolsysZwaveThermostatEntity


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
        entities.append(ZoneSensor_LatestDBM(QolsysPanel, zone.zone_id, config_entry.unique_id))
        entities.append(ZoneSensor_AverageDBM(QolsysPanel, zone.zone_id, config_entry.unique_id))

    # Add Z-Wave Dimmer Sensors
    for dimmer in QolsysPanel.state.zwave_dimmers:
        # Addu Battery Value if battery présent
        if dimmer.node_battery_level_value != "-1":
            entities.append(DimmerSensor_BatteryValue(QolsysPanel,dimmer.node_id,config_entry.unique_id))

    # Add Z-Wave Lock Sensors
    for lock in QolsysPanel.state.zwave_locks:
        if lock.node_battery_level_value != "-1":
            entities.append(LockSensor_BatteryValue(QolsysPanel,lock.node_id,config_entry.unique_id))

    # Add Z-Wave Thermostat Sensors
    for thermostat in QolsysPanel.state.zwave_thermostats:
        if thermostat.node_battery_level_value != "-1":
            entities.append(ThermostatSensor_BatteryValue(QolsysPanel,thermostat.node_id,config_entry.unique_id))

    async_add_entities(entities)


class ZoneSensor_LatestDBM(QolsysZoneEntity, SensorEntity):
    """A sensor entity for the latest DBM of a zone."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, QolsysPanel: qolsys_controller, zone_id: int, unique_id: str) -> None:
        """Set up a binary sensor entity for a zone battery status."""
        super().__init__(QolsysPanel, zone_id, unique_id)
        self._attr_unique_id = f"{self._zone_unique_id}_latestdBm"
        self._attr_name = 'Latest dBm'
        self._attr_native_unit_of_measurement = 'dBm'
        self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return the latest dBm value of the zone."""
        if self._zone.latestdBm is None or self._zone.latestdBm == '':
            return 0
        else:
            return int(self._zone.latestdBm)

class ZoneSensor_AverageDBM(QolsysZoneEntity, SensorEntity):
    """A sensor entity for the average DBM of a zone."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, QolsysPanel: qolsys_controller, zone_id: int, unique_id: str) -> None:
        """Set up a binary sensor entity for a zone battery status."""
        super().__init__(QolsysPanel, zone_id, unique_id)
        self._attr_unique_id = f"{self._zone_unique_id}_averagedBm"
        self._attr_name = 'Average dBm'
        self._attr_native_unit_of_measurement = 'dBm'
        self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return the latest dBm value of the zone."""
        return int(self._zone.averagedBm)
    
class DimmerSensor_BatteryValue(QolsysZwaveDimmerEntity, SensorEntity):
    """A sensor entity for a dimmer battery value."""

    def __init__(self, QolsysPanel: qolsys_controller, node_id: int, unique_id: str) -> None:
        """Set up a sensor entity for a dimmer battery value."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = f"{self._zwave_dimmer_unique_id}_battery_value"
        self._attr_name = 'Battery'
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return dimmer battery value."""
        try:
            value = int(self._dimmer.node_battery_level_value)
            if value >= 0 and value <= 100:
                return value
            else:
                return None
        
        except ValueError:
            return None
        
class LockSensor_BatteryValue(QolsysZwaveLockEntity, SensorEntity):
    """A sensor entity for a lock battery value."""

    def __init__(self, QolsysPanel: qolsys_controller, node_id: int, unique_id: str) -> None:
        """Set up a sensor entity for a lock battery value."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = f"{self._zwave_lock_unique_id}_battery_value"
        self._attr_name = 'Battery'
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return lock battery value."""
        try:
            value = int(self._lock.node_battery_level_value)
            if value >= 0 and value <= 100:
                return value
            else:
                return None
        
        except ValueError:
            return None

class ThermostatSensor_BatteryValue(QolsysZwaveThermostatEntity, SensorEntity):
    """A sensor entity for a thermostat battery value."""

    def __init__(self, QolsysPanel: qolsys_controller, node_id: int, unique_id: str) -> None:
        """Set up a sensor entity for a thermostat battery value."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = f"{self._zwave_thermostat_unique_id}_battery_value"
        self._attr_name = 'Battery'
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return thermostat battery value."""
        try:
            value = int(self._thermostat.node_battery_level_value)
            if value >= 0 and value <= 100:
                return value
            else:
                return None
        
        except ValueError:
            return None



