"""Support for Qolsys Panel."""

from __future__ import annotations

import logging
import threading
from typing import cast

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .vendor.qolsys_controller import qolsys_controller
from .vendor.qolsys_controller.automation.device import QolsysAutomationDevice
from .vendor.qolsys_controller.automation.protocol_status import StatusProtocol
from .vendor.qolsys_controller.enum_qolsys import ControllerState, QolsysNotification
from .vendor.qolsys_controller.observable import Event
from .vendor.qolsys_controller.partition import QolsysPartition
from .vendor.qolsys_controller.zone import QolsysZone


class QolsysPanelEntity(Entity):
    """A base entity for Qolsys Panel Entity."""

    _attr_has_entity_name = True

    def __init__(self, QolsysPanel: qolsys_controller, unique_id: str) -> None:
        """Set up a entity for a Qolsys Panel."""
        self.QolsysPanel = QolsysPanel
        self._panel_unique_id = unique_id
        self._attr_should_poll = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Johnson Controls",
        )

    @property
    def device_info(self) -> DeviceInfo | None:
        """Device info, with child devices linked to the panel by registry id.

        `via_device` (an identifier tuple) is deprecated in Home Assistant 2026.9
        and, when an entity is re-added from the settings UI, the deprecation is
        raised as an error rather than logged, which is how the alarm entity
        failed to come back after a rename (2026-09-07). `via_device_id` needs the
        parent's registry id, which is only known at read time; the panel device
        is created in async_setup_entry before any platform loads, so the lookup
        succeeds. If it ever misses, the child is simply left unlinked.
        """
        info = self._attr_device_info
        if info is None:
            return None
        if (DOMAIN, self._panel_unique_id) in info.get("identifiers", set()):
            return info  # this IS the panel device
        linked = DeviceInfo(**info)
        platform = getattr(self, "platform", None)
        entry = getattr(platform, "config_entry", None) if platform else None
        if getattr(self, "hass", None) is not None and entry is not None:
            parent = dr.async_get(self.hass).async_get_device_by_identifier(
                (DOMAIN, self._panel_unique_id), entry.entry_id
            )
            if parent is not None:
                linked["via_device_id"] = parent.id
        return linked

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.QolsysPanel.controller_state == ControllerState.CONNECTED

    def _on_loop_thread(self) -> bool:
        """True when running on Home Assistant's event-loop thread."""
        hass = self.hass
        return hass is None or threading.get_ident() == hass.loop_thread_id

    def _write_state_threadsafe(self) -> None:
        """Write the state from whichever thread the library notified on.

        The library fires observers synchronously on the thread that changed
        the model, and that is not always the event loop: a failed arm on
        2026-09-07 notified from an executor thread, HA raised on
        async_write_ha_state, the observer logged the error and the update was
        dropped. Off the loop, hand the write to the loop instead.
        """
        if self._on_loop_thread():
            self.async_write_ha_state()
        else:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    def _handle_update(self, event: Event | None = None) -> None:
        """Write the new state.

        The event payload is unused: every property re-reads the library model.
        Registered instead of schedule_update_ha_state, whose single positional
        parameter made the observable pass the Event as force_refresh=True, so
        every zone opening and panel ping built a coroutine and a Task for an
        update method that does not exist (audit M4).
        """
        self._write_state_threadsafe()

    async def async_added_to_hass(self) -> None:
        """Observe connection_status changes."""
        self.QolsysPanel.state.register(
            QolsysNotification.PANEL_STATUS_UPDATE, self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing connection_status changes."""
        self.QolsysPanel.state.unregister(
            QolsysNotification.PANEL_STATUS_UPDATE, self._handle_update
        )


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
        partition = QolsysPanel.state.partition(self._partition_id)
        if partition is None:
            _LOGGER.error("Invalid partition_id:%s", self._partition_id)
            raise ValueError(f"Unknown partition id: {self._partition_id}")
        self._partition: QolsysPartition = partition
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._partition_unique_id)},
            name=f"Partition{self._partition_id} - {self._partition.name}",
            model="Qolsys Partition",
            manufacturer="Johnson Controls",
        )

    async def async_added_to_hass(self) -> None:
        """Observe changes."""
        await super().async_added_to_hass()
        self._partition.register(
            QolsysNotification.PARTITION_UPDATE, self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing changes."""
        await super().async_will_remove_from_hass()
        self._partition.unregister(
            QolsysNotification.PARTITION_UPDATE, self._handle_update
        )


class QolsysZoneEntity(QolsysPanelEntity):
    """Qolsys Zone Entity."""

    def __init__(
        self, QolsysPanel: qolsys_controller, zone_id: str, unique_id: str
    ) -> None:
        """Set up Qolsys Zone."""
        super().__init__(QolsysPanel, unique_id)
        self._zone_id = zone_id
        self._zone_unique_id = f"{unique_id}_zone{zone_id}"
        zone = QolsysPanel.state.zone(self._zone_id)
        if zone is None:
            _LOGGER.error("Invalid zone_id:%s", self._zone_id)
            raise ValueError(f"Unknown zone id: {self._zone_id}")
        self._zone: QolsysZone = zone
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._zone_unique_id)},
            name=f"Zone{self._zone_id} - {self._zone.sensorname}",
            model="Qolsys Zone",
            manufacturer="Johnson Controls",
        )

    async def async_added_to_hass(self) -> None:
        """Observe changes."""
        await super().async_added_to_hass()
        self._zone.register(
            QolsysNotification.ZONE_UPDATE, self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing changes."""
        await super().async_will_remove_from_hass()
        self._zone.unregister(
            QolsysNotification.ZONE_UPDATE, self._handle_update
        )


class QolsysAutomationDeviceEntity(QolsysPanelEntity):
    """Qolsys Automation Device Entity."""

    def __init__(
        self, QolsysPanel: qolsys_controller, virtual_node_id: str, unique_id: str
    ) -> None:
        """Set up Qolsys Automation Device Entity."""
        super().__init__(QolsysPanel, unique_id)
        self._virtual_node_id = virtual_node_id
        self._autdev_unique_id = f"{unique_id}_autdev_{virtual_node_id}"
        autdev = QolsysPanel.state.automation_device(virtual_node_id)

        if autdev is None:
            _LOGGER.error("Invalid AutDev virtual_node_id:%s", virtual_node_id)
            raise ValueError(
                f"Unknown automation device virtual_node_id: {virtual_node_id}"
            )
        self._autdev: QolsysAutomationDevice = autdev

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._autdev_unique_id)},
            name=f"Device{virtual_node_id} - {self._autdev.device_type} - {self._autdev.device_name}",
            model="Automation Device [%s]" % self._autdev.protocol,
            manufacturer="Johnson Controls",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        status_services = cast(
            "list[StatusProtocol]",
            self._autdev.service_get_protocol(StatusProtocol),  # type: ignore[type-abstract]
        )
        for service in status_services:
            if service.is_malfunctioning:
                return False

        return self.QolsysPanel.controller_state == ControllerState.CONNECTED

    async def async_added_to_hass(self) -> None:
        """Observe changes."""
        await super().async_added_to_hass()
        self._autdev.register(
            QolsysNotification.AUTOMATION_UPDATE, self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing changes."""
        await super().async_will_remove_from_hass()
        self._autdev.unregister(
            QolsysNotification.AUTOMATION_UPDATE, self._handle_update
        )


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
        self.QolsysPanel.state.register(
            QolsysNotification.PANEL_SETTINGS_UPDATE, self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing changes."""
        await super().async_will_remove_from_hass()
        self.QolsysPanel.state.unregister(
            QolsysNotification.PANEL_SETTINGS_UPDATE, self._handle_update
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
        self.QolsysPanel.state.weather.register(
            QolsysNotification.WEATHER_UPDATE, self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing changes."""
        await super().async_will_remove_from_hass()
        self.QolsysPanel.state.weather.unregister(
            QolsysNotification.WEATHER_UPDATE, self._handle_update
        )
