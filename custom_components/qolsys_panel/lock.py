"""Support for Qolsys Z-Wave Locks."""

from __future__ import annotations

import logging


from typing import Any

from qolsys_controller import qolsys_controller
from qolsys_controller.automation.protocol_lock import LockProtocol
from qolsys_controller.automation.service_lock import LockService

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysAutomationDeviceEntity, QolsysZwaveEntity
from .types import QolsysPanelConfigEntry


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Z-Wave Lock entities."""
    QolsysPanel = config_entry.runtime_data
    entities: list[QolsysZwaveEntity] = []

    # Append Z-Wave Locks
    for lock in QolsysPanel.state.zwave_locks:
        entities.append(ZWaveLock(QolsysPanel, lock.node_id, config_entry.unique_id))

    # Append Automation Device Locks
    for device in QolsysPanel.state.automation_devices:
        for service in device.service_get_protocol(LockProtocol):
            entities.append(
                AutomationDeviceLock(
                    QolsysPanel,
                    device.virtual_node_id,
                    service.endpoint,
                    config_entry.unique_id,
                )
            )

    async_add_entities(entities)


class ZWaveLock(QolsysZwaveEntity, LockEntity):
    """An Z-Wave Lock entity for a qolsys panel."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: str, unique_id: str
    ) -> None:
        """Initialise a Qolsys Z-Wave Device entity."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = self._zwave_unique_id
        self._value_is_locking = False
        self._value_is_unlocking = False

    @property
    def is_locked(self) -> bool:
        return self._node.is_locked()

    @property
    def is_locking(self) -> bool:
        return self._value_is_locking

    @property
    def is_unlocking(self) -> bool:
        return self._value_is_unlocking

    async def async_lock(self, **kwargs: Any):
        self._value_is_locking = True
        self._value_is_unlocking = False
        self.async_schedule_update_ha_state()
        await self._node.lock()
        self._value_is_locking = False

    async def async_unlock(self, **kwargs: Any):
        self._value_is_unlocking = True
        self._value_is_locking = False
        self.async_schedule_update_ha_state()
        await self._node.unlock()
        self._value_is_unlocking = False


class AutomationDeviceLock(QolsysAutomationDeviceEntity, LockEntity):
    """An Automation Device Lock entity for a qolsys panel."""

    _attr_has_entity_name = True
    _attr_name = None

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
        return self._service.is_openning

    @property
    def is_open(self) -> bool:
        return self._service.is_open

    async def async_lock(self, **kwargs: Any):
        await self._service.lock()

    async def async_unlock(self, **kwargs: Any):
        await self._service.unlock()

    async def async_open(self, **kwargs: Any):
        await self._service.open()
