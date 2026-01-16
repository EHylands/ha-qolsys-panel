"""Support for Qolsys Valve."""

from __future__ import annotations

import logging

from homeassistant.components.valve import (
    ValveEntity,
    ValveEntityFeature,
    ValveDeviceClass,
)

from qolsys_controller import qolsys_controller
from qolsys_controller.zwave_water_valve import QolsysWaterValve
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
    """Set up Valves."""
    QolsysPanel = config_entry.runtime_data

    entities: list[ValveEntity] = []

    # Add Z-Wave Valves
    for valve in QolsysPanel.state.zwave_water_valves:
        entities.append(
            ZwaveDevice_Valve(QolsysPanel, valve.node_id, config_entry.unique_id)
        )

    async_add_entities(entities)


class ZwaveDevice_Valve(QolsysZwaveEntity, ValveEntity):
    """Z-Wave Valve Entity"""

    _attr_has_entity_name = True

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        node_id: str,
        unique_id: str,
    ) -> None:
        """Initialise a Z-Wave Water Valve."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = f"{self._zwave_unique_id}_water_valve"
        self.device_class = ValveDeviceClass.WATER
        self._attr_reports_position = False

        if ZwaveCommandClass.SwitchBinary in self._node.command_class_list:
            self._attr_supported_features |= (
                ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
            )

    async def async_open_valve(self) -> None:
        """Open the valve."""
        _LOGGER.debug("Open - Available Commands: %s", self._node.command_class_list)
        await self.QolsysPanel.command_zwave_switch_binary_set(self._node_id, True)

    async def async_close_valve(self) -> None:
        """Close valve."""
        _LOGGER.debug("Close - Available Commands: %s", self._node.command_class_list)
        await self.QolsysPanel.command_zwave_switch_binary_set(self._node_id, False)

    @property
    def is_closed(self) -> bool | None:
        return None
