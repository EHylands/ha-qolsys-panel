"""Support for Qolsys Panel."""

from __future__ import annotations

from qolsys_controller import qolsys_controller

from homeassistant.components.sensor import Entity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


class QolsysPanelEntity(Entity):
    """A base entity for a Qolsys Panel."""

    _attr_has_entity_name = True

    def __init__(self,
                 QolsysPanel:qolsys_controller,
                 unique_id:str
    ) -> None:
        """Set up a entity for a Qolsys Panel."""
        self.QolsysPanel = QolsysPanel
        self._attr_should_poll = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Johnson Controls",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.QolsysPanel.plugin.connected

    async def async_added_to_hass(self) -> None:
        """Observe connection_status changes."""
        self.QolsysPanel.plugin.connected_observer.register(
            self.schedule_update_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing connection_status changes."""
        self.QolsysPanel.plugin.connected_observer.unregister(
            self.schedule_update_ha_state
        )

class QolsysPartitionEntity(QolsysPanelEntity):
    """Qolsys Partiton Entity."""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        partition_id: str,
        unique_id: str,
    ) -> None:
        """Set up Qolsys Partition."""
        super().__init__(QolsysPanel, unique_id)
        self._partition_id = partition_id
        self._partition_unique_id = f"{unique_id}_partition{partition_id}"
        self._partition = QolsysPanel.state.partition(self._partition_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._partition_unique_id)},
            name=f"Partition{self._partition_id} - {self._partition.name}",
            model="Qolsys Partition",
            manufacturer="Johnson Controls",
            via_device=(DOMAIN, unique_id),
        )

    async def async_added_to_hass(self) -> None:
        """Observe changes."""
        await super().async_added_to_hass()
        self._partition.register(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing changes."""
        await super().async_will_remove_from_hass()
        self._partition.unregister(self.schedule_update_ha_state)

class QolsysZoneEntity(QolsysPanelEntity):
    """Qolsys Zone Entity."""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        zone_id: str,
        unique_id: str
    ) -> None:
        """Set up Qolsys Zone."""
        super().__init__(QolsysPanel, unique_id)
        self._zone_id = zone_id
        self._zone_unique_id = f"{unique_id}_zone{zone_id}"
        self._zone = QolsysPanel.state.zone(self._zone_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._zone_unique_id)},
            name=f"Zone{self._zone_id} - {self._zone.sensorname}",
            model="Qolsys Zone",
            manufacturer="Johnson Controls",
            via_device=(DOMAIN, unique_id),
        )

    async def async_added_to_hass(self) -> None:
        """Observe changes."""
        await super().async_added_to_hass()
        self._zone.register(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing changes."""
        await super().async_will_remove_from_hass()
        self._zone.unregister(self.schedule_update_ha_state)

class QolsysPanelSensorEntity(QolsysPanelEntity):
    """Qolsys Panel Sensor Entity (Panel diagnostic sensors)."""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        key: str,
        unique_id: str
    ) -> None:
        """Set up a Qolsys Panel Sensor."""
        super().__init__(QolsysPanel, unique_id)
        self._panelsensor_unique_id = f"{unique_id}_panelsensor_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Johnson Controls",
            model=f"Qolsys IQ Panel ({QolsysPanel.panel.HARDWARE_VERSION})",
        )

    async def async_added_to_hass(self) -> None:
        """Observe changes."""
        await super().async_added_to_hass()
        self.QolsysPanel.panel.settings_panel_observer.register(
            self.schedule_update_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing changes."""
        await super().async_will_remove_from_hass()
        self.QolsysPanel.panel.settings_panel_observer.unregister(
            self.schedule_update_ha_state
        )

class QolsysZwaveDimmerEntity(QolsysPanelEntity):
    """Z-Wave Dimmer Entity."""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        node_id: str,
        unique_id: str
    ) -> None:
        """Set up a Qolsys Z-Wave Dimmer ."""
        super().__init__(QolsysPanel, unique_id)
        self._zwave_dimmer_unique_id = f"{unique_id}_zwave_dimmer{node_id}"
        self._dimmer = QolsysPanel.state.zwave_device(node_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._zwave_dimmer_unique_id)},
            manufacturer="Johnson Controls",
            name=f"Z-Wave{node_id} - Dimmer - {self._dimmer.dimmer_name}",
            model="Qolsys Z-Wave Dimmer",
            via_device=(DOMAIN, unique_id),
        )

    async def async_added_to_hass(self) -> None:
        """Observe changes."""
        await super().async_added_to_hass()
        self._dimmer.register(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing changes."""
        await super().async_will_remove_from_hass()
        self._dimmer.unregister(self.schedule_update_ha_state)

class QolsysZwaveLockEntity(QolsysPanelEntity):
    """Z-Wave Lock Entity."""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        node_id: str,
        unique_id: str
    ) -> None:
        """Set up a z-wave lock ."""
        super().__init__(QolsysPanel, unique_id)
        self._zwave_lock_unique_id = f"{unique_id}_zwave_lock{node_id}"
        self._locks = QolsysPanel.state.zwave_device(node_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._zwave_lock_unique_id)},
            manufacturer="Johnson Controls",
            name=f"Z-Wave{node_id} - Lock - {self.lock.lock_name}",
            model="Qolsys Z-Wave Lock",
            via_device=(DOMAIN, unique_id),
        )

    async def async_added_to_hass(self) -> None:
        """Observe changes."""
        await super().async_added_to_hass()
        self._lock.register(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing changes."""
        await super().async_will_remove_from_hass()
        self._lock.unregister(self.schedule_update_ha_state)

class QolsysZwaveThermostatEntity(QolsysPanelEntity):
    """Z-Wave Thermostat Entity."""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        node_id: str,
        unique_id: str
    ) -> None:
        """Set up a Z-Wave Thermostat ."""
        super().__init__(QolsysPanel, unique_id)
        self._zwave_thermostat_unique_id = f"{unique_id}_zwave_thermostat{node_id}"
        self._thermostat = QolsysPanel.state.zwave_device(node_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._zwave_dimmer_unique_id)},
            manufacturer="Johnson Controls",
            name=f"Z-Wave{node_id} - Thermostat - {self.lock.lock_name}",
            model="Qolsys Z-Wave Thermostat",
            via_device=(DOMAIN, unique_id),
        )

    async def async_added_to_hass(self) -> None:
        """Observe changes."""
        await super().async_added_to_hass()
        self._thermostat.register(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing changes."""
        await super().async_will_remove_from_hass()
        self._thermostat.unregister(self.schedule_update_ha_state)
