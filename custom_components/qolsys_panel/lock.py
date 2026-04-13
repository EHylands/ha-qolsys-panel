"""Support for Qolsys Locks."""

from __future__ import annotations

import logging


from typing import Any

from qolsys_controller import qolsys_controller
from qolsys_controller.automation.service_lock import LockService

from homeassistant.components.lock import LockEntity, LockEntityFeature
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
    QolsysPanel = config_entry.runtime_data
    entities: list[LockEntity] = []

    # Append Automation Device Locks
    for device in QolsysPanel.state.automation_devices:
        for service in device.service_get_protocol(LockService):
            entities.append(
                AutomationDeviceLock(
                    QolsysPanel,
                    device.virtual_node_id,
                    service.endpoint,
                    config_entry.unique_id,
                )
            )

    async_add_entities(entities)


class AutomationDeviceLock(QolsysAutomationDeviceEntity, LockEntity):
    """Automation Device Lock Entity."""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        virtual_node_id: str,
        endpoint: int,
        unique_id: str,
    ) -> None:
        super().__init__(QolsysPanel, virtual_node_id, unique_id)
        self._attr_unique_id = f"{self._autdev_unique_id}_lock{endpoint}"
        self._service = self._autdev.service_get(LockService, endpoint)
        self._attr_name = f"Lock{'' if endpoint == 0 else endpoint} - {self._service.automation_device.device_name}"

        self._attr_supported_features = 0
        if self._service.supports_open():
            self._attr_supported_features |= LockEntityFeature.OPEN

    @property
    def is_locked(self) -> bool:
        return self._service.is_locked

    @property
    def is_locking(self) -> bool:
        return self._service.is_locking

    @property
    def is_unlocking(self) -> bool:
        return self._service.is_unlocking

    @property
    def is_jammed(self) -> bool:
        return self._service.is_jammed

    @property
    def is_opening(self) -> bool:
        return self._service.is_opening

    @property
    def is_open(self) -> bool:
        return self._service.is_open

    async def async_lock(self, **kwargs: Any):
        await self._service.lock()

    async def async_unlock(self, **kwargs: Any):
        await self._service.unlock()

    async def async_open(self, **kwargs: Any):
        await self._service.open()
