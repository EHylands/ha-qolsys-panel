"""Sensor platform for Qolsys Panel."""

from __future__ import annotations

import logging
from typing import Type


from qolsys_controller import qolsys_controller
from qolsys_controller.enum_zwave import (
    MeterType,
    ZWaveElectricMeterScale,
    ZWaveMultilevelSensorScale,
    ZWaveUnknownMeterScale,
)
from qolsys_controller.zwave_service_meter import (
    QolsysZwaveServiceMeter,
    QolsysZwaveMeterSensor,
)
from qolsys_controller.zwave_service_multilevelsensor import (
    QolsysZwaveServiceMultilevelSensor,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from enum import IntEnum


from . import QolsysPanelConfigEntry
from .entity import (
    QolsysZoneEntity,
    QolsysZwaveEntity,
)

_LOGGER = logging.getLogger(__name__)


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

    # Add Z-Wave Device Sensors
    for device in QolsysPanel.state.zwave_devices:
        # Battery Sensor
        if device.is_battery_enabled():
            entities.append(
                ZwaveDevice_BatteryValue(
                    QolsysPanel, device.node_id, config_entry.unique_id
                )
            )

        # Z-Wave Meter
        if device.is_service_meter_enabled():
            for meter_endpoint in device.meter_endpoints:
                for meter_sensor in meter_endpoint.sensors:
                    entities.append(
                        ZwaveDevice_MeterValue(
                            QolsysPanel,
                            device.node_id,
                            meter_endpoint.endpoint,
                            meter_endpoint._meter_type,
                            meter_sensor.scale,
                            config_entry.unique_id,
                        )
                    )
        # Z-Wave Multilevel Sensor
        if device.is_service_multilevelsensor_enabled():
            for sensor_endpoint in device.multilevelsensor_endpoints:
                for sensor in sensor_endpoint.sensors:
                    entities.append(
                        ZwaveDevice_MultilevelSensorValue(
                            QolsysPanel,
                            device.node_id,
                            sensor_endpoint.endpoint,
                            sensor.unit,
                            config_entry.unique_id,
                        )
                    )

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


class ZwaveDevice_BatteryValue(QolsysZwaveEntity, SensorEntity):
    """A sensor entity for a dimmer battery value."""

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: int, unique_id: str
    ) -> None:
        """Set up a sensor entity for a z-wave device battery value."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = f"{self._zwave_unique_id}_battery_value"
        self._attr_translation_key = "battery"
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return z-wave device battery value."""
        return self._node.node_battery_level_value


class ZwaveDevice_MeterValue(QolsysZwaveEntity, SensorEntity):
    """A sensor entity for a z-wave meter value."""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        node_id: int,
        endpoint: str,
        meter_type: MeterType,
        scale: IntEnum,
        unique_id: str,
    ) -> None:
        """Set up a sensor entity for a z-wave meter value."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._meter_type: MeterType = meter_type
        self._endpoint: str = endpoint
        self._scale: IntEnum = scale
        self._attr_unique_id = (
            f"{self._zwave_unique_id}_{meter_type.name}_{endpoint}_{self._scale.name}"
        )
        self._attr_suggested_display_precision = 0
        self._scale_type: Type[IntEnum] = ZWaveUnknownMeterScale
        self._meter: QolsysZwaveServiceMeter | None = None
        self._meter_sensor: QolsysZwaveMeterSensor | None = None

        for meter_endpoint in self._node.meter_endpoints:
            if meter_endpoint.endpoint == endpoint:
                self._meter = meter_endpoint
                self._scale_type = self._meter._scale_type
                self._meter_sensor = self._meter.get_sensor(scale)
                break

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class of this entity."""

        match self._scale_type(self._scale):
            case ZWaveElectricMeterScale.WATTS:
                return SensorStateClass.MEASUREMENT
            case ZWaveElectricMeterScale.KWH:
                return SensorStateClass.TOTAL_INCREASING
            case ZWaveElectricMeterScale.POWER_FACTOR:
                return SensorStateClass.MEASUREMENT
            case ZWaveElectricMeterScale.KVAR:
                return SensorStateClass.TOTAL
            case ZWaveElectricMeterScale.VOLTS:
                return SensorStateClass.MEASUREMENT
            case ZWaveElectricMeterScale.KVARH:
                return SensorStateClass.TOTAL
            case ZWaveElectricMeterScale.KVAH:
                return SensorStateClass.TOTAL
            case ZWaveElectricMeterScale.AMPS:
                return SensorStateClass.MEASUREMENT
            case ZWaveElectricMeterScale.PULSE_COUNT:
                return SensorStateClass.MEASUREMENT

        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str:
        scale_type = self._meter._scale_type

        if self._meter_type == MeterType.ELECTRIC_METER:
            match scale_type(self._scale):
                case ZWaveElectricMeterScale.WATTS:
                    return "W"
                case ZWaveElectricMeterScale.KWH:
                    return "kWh"
                case ZWaveElectricMeterScale.POWER_FACTOR:
                    return "%"
                case ZWaveElectricMeterScale.KVAR:
                    return "kvar"
                case ZWaveElectricMeterScale.VOLTS:
                    return "V"
                case ZWaveElectricMeterScale.KVARH:
                    return "kvarh"
                case ZWaveElectricMeterScale.KVAH:
                    return "Wh"
                case ZWaveElectricMeterScale.AMPS:
                    return "A"
                case ZWaveElectricMeterScale.PULSE_COUNT:
                    return "Hz"

            return None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        scale_type = self._scale_type

        if self._meter_type == MeterType.ELECTRIC_METER:
            match scale_type(self._scale):
                case ZWaveElectricMeterScale.WATTS:
                    return SensorDeviceClass.POWER
                case ZWaveElectricMeterScale.KWH:
                    return SensorDeviceClass.ENERGY
                case ZWaveElectricMeterScale.POWER_FACTOR:
                    return SensorDeviceClass.POWER_FACTOR
                case ZWaveElectricMeterScale.KVAR:
                    return SensorDeviceClass.REACTIVE_POWER
                case ZWaveElectricMeterScale.VOLTS:
                    return SensorDeviceClass.VOLTAGE
                case ZWaveElectricMeterScale.KVARH:
                    return SensorDeviceClass.REACTIVE_POWER  # Should be reactive_energy
                case ZWaveElectricMeterScale.KVAH:
                    return SensorDeviceClass.ENERGY
                case ZWaveElectricMeterScale.AMPS:
                    return SensorDeviceClass.CURRENT
                case ZWaveElectricMeterScale.PULSE_COUNT:
                    return SensorDeviceClass.FREQUENCY

            return None

    @property
    def native_value(self) -> int | None:
        """Return powermeter value."""
        return self._meter_sensor.value


class ZwaveDevice_MultilevelSensorValue(QolsysZwaveEntity, SensorEntity):
    """A sensor entity for a dimmer meter value."""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        node_id: int,
        endpoint: str,
        unit: ZWaveMultilevelSensorScale,
        unique_id: str,
    ) -> None:
        """Set up a sensor entity for a z-wave device multilevelsensor value."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = (
            f"{self._zwave_unique_id}_multilevelsensor_{endpoint}_{unit.name}"
        )
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._unit = unit
        self._endpoint: str = endpoint
        self._scale: ZWaveElectricMeterScale = unit
        self._multilevel_endpoint: QolsysZwaveServiceMultilevelSensor | None = None
        self._multilevel_sensor: QolsysZwaveServiceMultilevelSensor | None = None

        for sensor_endpoint in self._node.multilevelsensor_endpoints:
            if sensor_endpoint.endpoint == endpoint:
                self._multilevel_endpoint = sensor_endpoint
                self._multilevel_sensor = self._multilevel_endpoint.get_sensor(unit)
                break

    @property
    def native_unit_of_measurement(self) -> str:
        match self._unit:
            case ZWaveMultilevelSensorScale.TEMPERATURE_FAHRENHEIT:
                return "°F"
            case ZWaveMultilevelSensorScale.TEMPERATURE_CELSIUS:
                return "°C"
            case ZWaveMultilevelSensorScale.RELATIVE_HUMIDITY:
                return "%"

        return None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        match self._unit:
            case ZWaveMultilevelSensorScale.TEMPERATURE_CELSIUS:
                return SensorDeviceClass.TEMPERATURE

            case ZWaveMultilevelSensorScale.TEMPERATURE_FAHRENHEIT:
                return SensorDeviceClass.TEMPERATURE

            case ZWaveMultilevelSensorScale.RELATIVE_HUMIDITY:
                return SensorDeviceClass.HUMIDITY

        return None

    @property
    def native_value(self) -> float | None:
        """Return sensor value."""
        if self._multilevel_sensor is None:
            return None

        return self._multilevel_sensor.value
