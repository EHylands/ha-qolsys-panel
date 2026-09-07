"""Support for Qolsys Valve."""

from __future__ import annotations

import logging

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysAutomationDeviceEntity
from .types import QolsysPanelConfigEntry
from .vendor.qolsys_controller import qolsys_controller
from .vendor.qolsys_controller.automation.service_valve import ValveService

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Valves."""
    QolsysPanel = config_entry.runtime_data
    if (unique_id := config_entry.unique_id) is None:
        # A forwarded platform must not raise ConfigEntryNotReady: HA logs a
        # complaint rather than retrying, and __init__.async_setup_entry already
        # refuses a None unique_id before any platform is set up (review N5).
        raise ValueError("Config entry has no unique_id; re-add the integration")

    entities: list[ValveEntity] = []

    # Append Automation Device Valves
    for device in QolsysPanel.state.automation_devices:
        for service in device.service_get_protocol(ValveService):  # type: ignore[type-abstract]
            entities.append(
                AutomationDevice_Valve(
                    QolsysPanel,
                    device.virtual_node_id,
                    service.endpoint,
                    unique_id,
                )
            )

    async_add_entities(entities)


class AutomationDevice_Valve(QolsysAutomationDeviceEntity, ValveEntity):
    """Automation Device Valve Entity"""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        virtual_node_id: str,
        endpoint: int,
        unique_id: str,
    ) -> None:
        super().__init__(QolsysPanel, virtual_node_id, unique_id)
        self._attr_unique_id = f"{self._autdev_unique_id}_valve{endpoint}"
        service = self._autdev.service_get(ValveService, endpoint)  # type: ignore[type-abstract]
        if service is None:
            raise ValueError(
                f"Automation device {self._virtual_node_id} has no ValveService at endpoint {endpoint}"
            )
        self._service: ValveService = service
        self._attr_name = f"Valve{'' if endpoint == 0 else endpoint} - {self._service.automation_device.device_name}"
        self._attr_device_class = ValveDeviceClass.WATER

        if isinstance(self._service, ValveService):
            self._attr_supported_features = ValveEntityFeature(0)

            if self._service.supports_open():
                self._attr_supported_features |= ValveEntityFeature.OPEN

            if self._service.supports_close():
                self._attr_supported_features |= ValveEntityFeature.CLOSE

            if self._service.supports_stop():
                self._attr_supported_features |= ValveEntityFeature.STOP

            if self._service.supports_position():
                self._attr_supported_features |= ValveEntityFeature.SET_POSITION
                self._attr_reports_position = True

    async def async_open_valve(self) -> None:
        await self._service.open()

    async def async_close_valve(self) -> None:
        await self._service.close()

    async def async_stop_valve(self) -> None:
        await self._service.stop()

    async def async_set_valve_position(self, position: int) -> None:
        await self._service.set_position(position)

    @property
    def is_closed(self) -> bool | None:
        return self._service.is_closed
