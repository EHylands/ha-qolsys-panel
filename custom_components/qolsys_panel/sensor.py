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
from .entity import QolsysZoneEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    QolsysPanel = config_entry.runtime_data

    entities: list[SensorEntity] = [
        ZoneSensor_LatestDBM(QolsysPanel, zone.zone_id, config_entry.unique_id)
        for zone in QolsysPanel.state.zones
    ]

    entities.extend(
        ZoneSensor_AverageDBM(QolsysPanel, zone.zone_id, config_entry.unique_id)
        for zone in QolsysPanel.state.zones
    )

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



