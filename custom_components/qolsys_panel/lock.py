"""Support for Qolsys Z-Wave Locks."""

from __future__ import annotations

import logging

from typing import Any

from qolsys_controller import qolsys_controller

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysZwaveLockEntity
from .types import QolsysPanelConfigEntry

logging.basicConfig(level=logging.DEBUG,format='%(levelname)s - %(module)s: %(message)s')
LOGGER = logging.getLogger(__name__)

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
    #_attr_code_format = None

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: int, unique_id: str
    ) -> None:
        """Initialise a Qolsys Z-Wave Lock entity."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = self._zwave_lock_unique_id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.QolsysPanel.plugin.connected and self._lock.node_status == 'Normal'

    @property
    def is_locked(self) -> bool:
        return self._lock.lock_status == "Locked"
    
    async def async_lock(self, **kwargs: Any):
        LOGGER.debug("Sending Lock Command")
        await self.QolsysPanel.plugin.command_zwave_doorlock_set(node_id=self._lock.lock_node_id,locked=True)

    async def async_unlock(self, **kwargs: Any):
        LOGGER.debug("Sending Unlock Command")
        await self.QolsysPanel.plugin.command_zwave_doorlock_set(node_id=self._lock.lock_node_id,locked=False)
