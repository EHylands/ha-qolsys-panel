"""Support for Qolsys External Siren."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.siren import SirenEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysAutomationDeviceEntity
from .types import QolsysPanelConfigEntry
from .vendor.qolsys_controller import qolsys_controller
from .vendor.qolsys_controller.automation.service_siren import SirenService

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up External Sirens."""
    QolsysPanel = config_entry.runtime_data
    if (unique_id := config_entry.unique_id) is None:
        raise ConfigEntryNotReady(
            "Config entry has no unique_id; re-add the integration"
        )

    entities: list[SirenEntity] = []

    # Append Automation Device Sirens
    for device in QolsysPanel.state.automation_devices:
        for service in device.service_get_protocol(SirenService):  # type: ignore[type-abstract]
            entities.append(
                AutomationDevice_Siren(
                    QolsysPanel,
                    device.virtual_node_id,
                    service.endpoint,
                    unique_id,
                )
            )

    async_add_entities(entities)


class AutomationDevice_Siren(QolsysAutomationDeviceEntity, SirenEntity):
    """Automation Device Siren Entity"""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        virtual_node_id: str,
        endpoint: int,
        unique_id: str,
    ) -> None:
        super().__init__(QolsysPanel, virtual_node_id, unique_id)
        self._attr_unique_id = f"{self._autdev_unique_id}_siren{endpoint}"
        service = self._autdev.service_get(SirenService, endpoint)  # type: ignore[type-abstract]
        if service is None:
            raise ValueError(
                f"Automation device {self._virtual_node_id} has no SirenService at endpoint {endpoint}"
            )
        self._service: SirenService = service
        self._attr_name = f"Siren{'' if endpoint == 0 else endpoint} - {self._service.automation_device.device_name}"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._service.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._service.turn_off()

    @property
    def is_on(self) -> bool | None:
        return self._service.is_on
