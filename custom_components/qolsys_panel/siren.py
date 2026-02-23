"""Support for Qolsys Siren."""

from __future__ import annotations

import logging

from homeassistant.components.siren import (
    SirenEntity,
)

from qolsys_controller import qolsys_controller
from qolsys_controller.automation.service_siren import SirenService

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysAutomationDeviceEntity
from .types import QolsysPanelConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sirens."""
    QolsysPanel = config_entry.runtime_data

    entities: list[SirenEntity] = []

    # Append Automation Device Sirens
    for device in QolsysPanel.state.automation_devices:
        for service in device.service_get_protocol(SirenService):
            entities.append(
                AutomationDevice_Siren(
                    QolsysPanel,
                    device.virtual_node_id,
                    service.endpoint,
                    config_entry.unique_id,
                )
            )

    async_add_entities(entities)


class AutomationDevice_Siren(QolsysAutomationDeviceEntity, SirenEntity):
    """Automation Device Siren entity"""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        virtual_node_id: str,
        endpoint: int,
        unique_id: str,
    ) -> None:
        super().__init__(QolsysPanel, virtual_node_id, unique_id)
        self._attr_unique_id = f"{self._autdev_unique_id}_siren{endpoint}"
        self._service = self._autdev.service_get(SirenService, endpoint)
        self._attr_name = f"Siren{'' if endpoint == 0 else endpoint} - {self._service.automation_device.device_name}"

    async def async_turn_on(self, **kwargs) -> None:
        _LOGGER.debug("Turn On - Commands: %s", self._node.command_class_list)
        self._service.turn_on()

    async def async_turn_off(self, **kwargs):
        _LOGGER.debug("Turn Off - Commands: %s", self._node.command_class_list)
        self._service.turn_off()

    @property
    def is_on(self) -> bool | None:
        return self._service.is_on()
