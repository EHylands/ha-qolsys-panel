"""Sensor platform for Qolsys Panel."""

from __future__ import annotations

import logging


from qolsys_controller import qolsys_controller
from qolsys_controller.automation.service_sensor import SensorService, QolsysSensor
from qolsys_controller.automation.service_meter import MeterService, QolsysMeter
from qolsys_controller.enum import (
    QolsysSensorScale,
    QolsysMeterScale,
)

from qolsys_controller.enum import QolsysEvent

from qolsys_controller.automation.service_battery import BatteryService


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
    QolsysAutomationDeviceEntity,
    QolsysZoneEntity,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
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

        # Add PowerG+ Battery Level Sensor if enabled
        if zone.is_powerg_battery_level_enabled():
            entities.append(
                ZoneSensor_BatteryLevel(
                    QolsysPanel, zone.zone_id, config_entry.unique_id
                )
            )

        # Add PowerG+ Battery Voltage if enabled
        if zone.is_powerg_battery_voltage_enabled():
            entities.append(
                ZoneSensor_BatteryVoltage(
                    QolsysPanel, zone.zone_id, config_entry.unique_id
                )
            )

    # Add Automation Device Sensors
    for device in QolsysPanel.state.automation_devices:
        # Battery Level Value
        for service in device.service_get_protocol(BatteryService):
            if service.supports_battery_level():
                entities.append(
                    AutomationDevice_BatteryValue(
                        QolsysPanel,
                        device.virtual_node_id,
                        service.endpoint,
                        config_entry.unique_id,
                    )
                )

        # Multilevel Sensors
        for service in device.service_get_protocol(SensorService):
            for sensor in service.sensors:
                entities.append(
                    AutomationDevice_Sensor(
                        QolsysPanel,
                        device.virtual_node_id,
                        service.endpoint,
                        sensor.unit,
                        config_entry.unique_id,
                    )
                )

        # Meters
        for service in device.service_get_protocol(MeterService):
            for meter in service.meters:
                entities.append(
                    AutomationDevice_Meter(
                        QolsysPanel,
                        device.virtual_node_id,
                        service.endpoint,
                        meter.unit,
                        config_entry.unique_id,
                    )
                )

    async_add_entities(entities)

    # Add new Automation Device Sensor - Dynamic
    async def _automation_device_sensor_add(**kwargs) -> None:
        virtual_node_id = kwargs["virtual_node_id"]
        endpoint = kwargs["endpoint"]
        unit = kwargs["unit"]

        _LOGGER.debug(
            "EVENT_AUTDEV_SENSOR_ADD - virtual_node_id:%s, endpoint:%s, unit:%s",
            virtual_node_id,
            endpoint,
            unit,
        )

        new_sensor = AutomationDevice_Sensor(
            QolsysPanel, virtual_node_id, endpoint, unit, config_entry.unique_id
        )
        async_add_entities([new_sensor])

    _LOGGER.debug("Subscribing to: %s", QolsysEvent.EVENT_AUTDEV_SENSOR_ADD)
    QolsysPanel.state.state_observer.subscribe(
        QolsysEvent.EVENT_AUTDEV_SENSOR_ADD, _automation_device_sensor_add
    )


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


class ZoneSensor_BatteryLevel(QolsysZoneEntity, SensorEntity):
    """A sensor entity for a zone battery level value."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, QolsysPanel: qolsys_controller, zone_id: int, unique_id: str
    ) -> None:
        """Set up a sensor entity for a zone device battery level value."""
        super().__init__(QolsysPanel, zone_id, unique_id)
        self._attr_unique_id = f"{self._zone_unique_id}_powerg_battery_level"
        self._attr_translation_key = "powerg_battery_level"
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return zone device battery level value."""
        return self._zone.powerg_battery_level


class ZoneSensor_BatteryVoltage(QolsysZoneEntity, SensorEntity):
    """A sensor entity for a zone battery voltage value."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, QolsysPanel: qolsys_controller, zone_id: int, unique_id: str
    ) -> None:
        """Set up a sensor entity for a zone device battery voltage value."""
        super().__init__(QolsysPanel, zone_id, unique_id)
        self._attr_unique_id = f"{self._zone_unique_id}_powerg_battery_voltage"
        self._attr_translation_key = "powerg_battery_voltage"
        self._attr_native_unit_of_measurement = "V"
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_suggested_display_precision = 3
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return zone device battery voltage value."""
        return self._zone.powerg_battery_voltage

class AutomationDevice_BatteryValue(QolsysAutomationDeviceEntity, SensorEntity):
    """A sensor entity for an Automation Device battery level value."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        virtual_node_id: int,
        endpoint: int,
        unique_id: str,
    ) -> None:
        """Set up a sensor entity for an automation device battery level value."""
        super().__init__(QolsysPanel, virtual_node_id, unique_id)
        self._attr_unique_id = f"{self._autdev_unique_id}_battery_value{endpoint}"
        self._attr_translation_key = "battery"
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._service = self._autdev.service_get(BatteryService, endpoint)

    @property
    def native_value(self) -> int | None:
        return self._service.battery_level


class AutomationDevice_Sensor(QolsysAutomationDeviceEntity, SensorEntity):
    """An Automation Device sensor entity."""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        virtual_node_id: str,
        endpoint: int,
        unit: QolsysSensorScale,
        unique_id: str,
    ) -> None:
        super().__init__(QolsysPanel, virtual_node_id, unique_id)
        self._attr_unique_id = f"{self._autdev_unique_id}_sensor_{endpoint}_{unit.name}"
        self._attr_suggested_display_precision = 0
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._unit = unit
        self._endpoint: int = endpoint
        self._unit: QolsysSensorScale = unit
        self._service = self._autdev.service_get(SensorService, endpoint)
        self._sensor: QolsysSensor = self._service.sensor(unit)

    @property
    def native_unit_of_measurement(self) -> str:
        match self._unit:
            case QolsysSensorScale.TEMPERATURE_FAHRENHEIT:
                return "°F"
            case QolsysSensorScale.TEMPERATURE_CELSIUS:
                return "°C"
            case QolsysSensorScale.RELATIVE_HUMIDITY:
                return "%"

        return None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        match self._unit:
            case QolsysSensorScale.TEMPERATURE_FAHRENHEIT:
                return SensorDeviceClass.TEMPERATURE

            case QolsysSensorScale.TEMPERATURE_CELSIUS:
                return SensorDeviceClass.TEMPERATURE

            case QolsysSensorScale.RELATIVE_HUMIDITY:
                return SensorDeviceClass.HUMIDITY

        return None

    @property
    def native_value(self) -> float | None:
        return self._sensor.value


class AutomationDevice_Meter(QolsysAutomationDeviceEntity, SensorEntity):
    """An Automation Device Meter entity."""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        virtual_node_id: str,
        endpoint: int,
        unit: QolsysMeterScale,
        unique_id: str,
    ) -> None:
        super().__init__(QolsysPanel, virtual_node_id, unique_id)
        self._attr_unique_id = f"{self._autdev_unique_id}_meter{endpoint}_{unit.name}"
        self._attr_suggested_display_precision = 2
        self._unit: QolsysMeterScale = unit
        self._endpoint: int = endpoint
        self._service = self._autdev.service_get(MeterService, endpoint)
        self._meter: QolsysMeter = self._service.meter(unit)

    @property
    def native_unit_of_measurement(self) -> str:
        return self._unit.value

    @property
    def device_class(self) -> SensorDeviceClass | None:
        match self._unit:
            case QolsysMeterScale.KWH:
                return SensorDeviceClass.ENERGY
            case QolsysMeterScale.KVAH:
                return SensorDeviceClass.ENERGY
            case QolsysMeterScale.WATTS:
                return SensorDeviceClass.POWER
            case QolsysMeterScale.PULSE_COUNT:
                return SensorDeviceClass.FREQUENCY
            case QolsysMeterScale.VOLTS:
                return SensorDeviceClass.VOLTAGE
            case QolsysMeterScale.AMPS:
                return SensorDeviceClass.CURRENT
            case QolsysMeterScale.POWER_FACTOR:
                return SensorDeviceClass.POWER_FACTOR
            case QolsysMeterScale.KVAR:
                return SensorDeviceClass.REACTIVE_POWER
            case QolsysMeterScale.KVARH:
                return SensorDeviceClass.REACTIVE_POWER  # Should be reactive_energy
            case QolsysMeterScale.CUBIC_METERS:
                return SensorDeviceClass.VOLUME
            case QolsysMeterScale.CUBIC_FEET:
                return SensorDeviceClass.VOLUME
            case QolsysMeterScale.US_GALLONS:
                return SensorDeviceClass.VOLUME

        return None

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class of this entity."""
        match self._unit:
            case QolsysMeterScale.KWH:
                return SensorStateClass.TOTAL_INCREASING
            case QolsysMeterScale.KVAH:
                return SensorStateClass.TOTAL
            case QolsysMeterScale.WATTS:
                return SensorStateClass.MEASUREMENT
            case QolsysMeterScale.PULSE_COUNT:
                return SensorStateClass.TOTAL
            case QolsysMeterScale.VOLTS:
                return SensorStateClass.MEASUREMENT
            case QolsysMeterScale.AMPS:
                return SensorStateClass.MEASUREMENT
            case QolsysMeterScale.POWER_FACTOR:
                return SensorStateClass.MEASUREMENT
            case QolsysMeterScale.KVAR:
                return SensorStateClass.MEASUREMENT
            case QolsysMeterScale.KVARH:
                return SensorStateClass.TOTAL
            case QolsysMeterScale.CUBIC_METERS:
                return SensorStateClass.TOTAL_INCREASING
            case QolsysMeterScale.CUBIC_FEET:
                return SensorStateClass.TOTAL_INCREASING
            case QolsysMeterScale.US_GALLONS:
                return SensorStateClass.TOTAL_INCREASING

        return SensorStateClass.TOTAL

    @property
    def native_value(self) -> float | None:
        return self._meter.value
