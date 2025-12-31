"""Support for Qolsys Panel."""

from __future__ import annotations

from qolsys_controller import qolsys_controller
from qolsys_controller.zwave_thermostat import QolsysThermostat
from qolsys_controller.zwave_energy_clamp import QolsysEnergyClamp


from homeassistant.components.sensor import Entity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

import logging


class QolsysPanelEntity(Entity):
    """A base entity for Qolsys Panel Entity."""

    _attr_has_entity_name = True

    def __init__(self, QolsysPanel: qolsys_controller, unique_id: str) -> None:
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
        return self.QolsysPanel.connected

    async def async_added_to_hass(self) -> None:
        """Observe connection_status changes."""
        self.QolsysPanel.connected_observer.register(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing connection_status changes."""
        self.QolsysPanel.connected_observer.unregister(self.schedule_update_ha_state)


_LOGGER = logging.getLogger(__name__)


class QolsysPartitionEntity(QolsysPanelEntity):
    """Qolsys Partiton Entity."""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        partition_id: str,
        unique_id: str,
    ) -> None:
        """Set up Qolsys Partition Entity."""
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
        self, QolsysPanel: qolsys_controller, zone_id: str, unique_id: str
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


class QolsysZwaveEntity(QolsysPanelEntity):
    """Qolsys ZWave Entity."""

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: str, unique_id: str
    ) -> None:
        """Set up Qolsys ZWave Entity."""
        super().__init__(QolsysPanel, unique_id)
        self._node_id = node_id
        self._zwave_unique_id = f"{unique_id}_zwave{node_id}"
        self._node = QolsysPanel.state.zwave_device(node_id)

        if self._node is None:
            _LOGGER.error("Invalid Z-Wave node_id:%s", node_id)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._zwave_unique_id)},
            name=f"ZWave{node_id} - {self._node.node_type} - {self._node.node_name}",
            model="Qolsys Z-Wave Device",
            manufacturer="Johnson Controls",
            via_device=(DOMAIN, unique_id),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.QolsysPanel.connected and self._node.node_status == "Normal"

    async def async_added_to_hass(self) -> None:
        """Observe changes."""
        await super().async_added_to_hass()
        self._node.register(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing changes."""
        await super().async_will_remove_from_hass()
        self._node.unregister(self.schedule_update_ha_state)


class QolsysPanelSensorEntity(QolsysPanelEntity):
    """Qolsys Panel Sensor Entity (Panel diagnostic sensors)."""

    def __init__(
        self, QolsysPanel: qolsys_controller, key: str, unique_id: str
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


class QolsysWeatherEntity(QolsysPanelEntity):
    """Qolsys weather entity."""

    def __init__(self, QolsysPanel: qolsys_controller, unique_id: str) -> None:
        """Set up a Qolsys Weather Entity."""
        super().__init__(QolsysPanel, unique_id)
        self._weather_unique_id = f"{unique_id}_weather"
        self._weather = QolsysPanel.state.weather
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Johnson Controls",
            model=f"Qolsys IQ Panel ({QolsysPanel.panel.HARDWARE_VERSION})",
        )

    async def async_added_to_hass(self) -> None:
        """Observe changes."""
        await super().async_added_to_hass()
        self.QolsysPanel.state.weather.register(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing changes."""
        await super().async_will_remove_from_hass()
        self.QolsysPanel.state.weather.unregister(self.schedule_update_ha_state)
