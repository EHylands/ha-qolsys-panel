"""Support for Qolsys Siren."""

from __future__ import annotations

import logging

from homeassistant.components.siren import (
    SirenEntity,
)

from qolsys_controller import qolsys_controller
from qolsys_controller.zwave_extenal_siren import QolsysExternalSiren
from qolsys_controller.enum_zwave import ZwaveCommandClass

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from custom_components.qolsys_panel.entity import QolsysZwaveEntity

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

    # Add Z-Wave Sirens
    for siren in QolsysPanel.state.zwave_external_sirens:
        entities.append(
            ZwaveDevice_Siren(QolsysPanel, siren.node_id, config_entry.unique_id)
        )

    async_add_entities(entities)


class ZwaveDevice_Siren(QolsysZwaveEntity, SirenEntity):
    """Z-Wave Siren Entity"""

    _attr_name = None

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        node_id: str,
        unique_id: str,
    ) -> None:
        """Initialise a Z-Wave External Siren."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = f"{self._zwave_unique_id}_external_siren"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the device on."""
        _LOGGER.debug("Turn On - Commands: %s", self._node.command_class_list)
        if ZwaveCommandClass.SwitchBinary in self._node.command_class_list:
            await self.QolsysPanel.command_zwave_switch_binary_set(self._node_id, True)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        _LOGGER.debug("Turn Off - Commands: %s", self._node.command_class_list)
        if ZwaveCommandClass.SwitchBinary in self._node.command_class_list:
            await self.QolsysPanel.command_zwave_switch_binary_set(self._node_id, False)

    @property
    def is_on(self) -> bool | None:
        return None
