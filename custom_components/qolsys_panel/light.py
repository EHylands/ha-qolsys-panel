"""Support for Qolsys Z-Wave Dimmer."""

from __future__ import annotations

import logging

from typing import Any

from qolsys_controller import qolsys_controller
from qolsys_controller.enum_zwave import ZwaveDeviceClass
from qolsys_controller.zwave_dimmer import QolsysDimmer

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


from .types import QolsysPanelConfigEntry
from .entity import QolsysZwaveEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ligh for each Z-Wave dimmer."""
    QolsysPanel = config_entry.runtime_data
    entities: list[QolsysZwaveEntity] = []

    for dimmer in QolsysPanel.state.zwave_dimmers:
        entities.append(
            ZwaveDimmer(QolsysPanel, dimmer.dimmer_node_id, config_entry.unique_id)
        )

    async_add_entities(entities)


def to_qolsys_level(level):
    """Convert the given Home Assistant light level (0-255) to Qolsys (0-99)."""
    return int((level * 99) / 255)


def to_hass_level(level):
    """Convert the given Qolsys (0-99) light level to Home Assistant (0-255)."""
    return int((level * 255) / 99)


class ZwaveDimmer(QolsysZwaveEntity, LightEntity):
    """A Z-Wave dimmer light entity."""

    _attr_name = None

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: str, unique_id: str
    ) -> None:
        """Initialise a ZwaveDevice Entity."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = self._zwave_unique_id

        # check if z-wave node is a QolsysDimmer
        if not isinstance(self._node, QolsysDimmer):
            _LOGGER.error(
                f"ZWave{self._node_id} is not a QolsysDimmer:{type(self._node)}"
            )
            return

        if self._node.generic_device_type in (
            ZwaveDeviceClass.SwitchBinary,
            ZwaveDeviceClass.RemoteSwitchBinary,
        ):
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}
        else:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        brightness = 255

        if ATTR_BRIGHTNESS in kwargs:
            brightness = to_qolsys_level(kwargs[ATTR_BRIGHTNESS])

        if self._node.generic_device_type in (
            ZwaveDeviceClass.SwitchBinary,
            ZwaveDeviceClass.RemoteSwitchBinary,
        ):
            await self.QolsysPanel.command_zwave_switch_binary_set(
                self._node.node_id, True
            )
        else:
            await self.QolsysPanel.command_zwave_switch_multilevel_set(
                self._node.node_id, brightness
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        if self._node.generic_device_type in (
            ZwaveDeviceClass.SwitchBinary,
            ZwaveDeviceClass.RemoteSwitchBinary,
        ):
            await self.QolsysPanel.command_zwave_switch_binary_set(
                self._node.node_id, False
            )
        else:
            await self.QolsysPanel.command_zwave_switch_multilevel_set(
                self._node.node_id, 0
            )

    @property
    def is_on(self) -> bool:
        """Return if the light is on."""
        return self._node.is_on()

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        return to_hass_level(int(self._node.dimmer_level))
