"""Support for Qolsys Panel Scene."""

from __future__ import annotations

from typing import Any

from qolsys_controller import qolsys_controller
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.components.scene import Scene

from .types import QolsysPanelConfigEntry
from .entity import QolsysPanelEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up scenes."""
    QolsysPanel = config_entry.runtime_data

    async_add_entities(
        QolsysPanelScene(
            QolsysPanel,
            scene.scene_id,
            config_entry.unique_id,
        )
        for scene in QolsysPanel.state.scenes
    )

class QolsysPanelScene(Scene,QolsysPanelEntity):
    """An scene entity for a qolsys panel."""

    _attr_has_entity_name = True
    
    def __init__(
        self, QolsysPanel: qolsys_controller, scene_id:str, unique_id: str
    ) -> None:
        """Initialise a Qolsys Scene entity."""
        super().__init__(QolsysPanel, unique_id)
        self._attr_unique_id = f"{unique_id}_scene_{scene_id}"
        self._scene_id = scene_id
        self._scene =  QolsysPanel.state.scene(scene_id)
        if self._scene is not None:
            self._attr_name = self._scene.name

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene. Try to get entities into requested state."""
        await self.QolsysPanel.plugin.command_execute_scene(self._scene_id)
        

    


