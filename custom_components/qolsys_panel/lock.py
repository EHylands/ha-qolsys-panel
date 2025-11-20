"""Support for Qolsys Z-Wave Locks."""

from __future__ import annotations

from typing import Any

from qolsys_controller import qolsys_controller

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysZwaveLockEntity
from .types import QolsysPanelConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Z-Wave Lock entities."""
    QolsysPanel = config_entry.runtime_data
    entities: list[QolsysZwaveLockEntity] = []

    for lock in QolsysPanel.state.zwave_locks:
        entities.append(ZWaveLock(QolsysPanel,lock.node_id,config_entry.unique_id))

    async_add_entities(entities)

class ZWaveLock(QolsysZwaveLockEntity, LockEntity):
    """An Z-Wave Lock entity for a qolsys panel."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, 
        QolsysPanel: qolsys_controller, 
        node_id: str, 
        unique_id: str
    ) -> None:
        """Initialise a Qolsys Z-Wave Lock entity."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = self._zwave_lock_unique_id
        self._value_is_locking = False
        self._value_is_unlocking = False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.QolsysPanel.connected and self._lock.node_status == 'Normal'

    @property
    def is_locked(self) -> bool:
        return self._lock.lock_status == "Locked"
    
    @property
    def is_locking(self) -> bool:
        return self._value_is_locking
        
    @property
    def is_unlocking(self) -> bool:
        return self._value_is_unlocking

    async def async_lock(self, **kwargs: Any):
        node_id = self._lock.lock_node_id
        locked = True
        self._value_is_locking = True
        self._value_is_unlocking = False
        self.async_schedule_update_ha_state()
        await self.QolsysPanel.command_zwave_doorlock_set(node_id=node_id,locked=locked)
        self._value_is_locking = False

    async def async_unlock(self, **kwargs: Any):
        node_id = self._lock.lock_node_id
        locked = False
        self._value_is_unlocking = True
        self._value_is_locking = False
        self.async_schedule_update_ha_state()
        await self.QolsysPanel.command_zwave_doorlock_set(node_id=node_id,locked=locked)
        self._value_is_unlocking = False
