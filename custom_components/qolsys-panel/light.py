"""Support for Qolsys Z-Wave Dimmer."""

from __future__ import annotations

from typing import Any

from qolsys_controller import qolsys_controller

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysZwaveDimmerEntity
from .types import QolsysPanelConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ligh for each Z-Wave dimmer."""
    QolsysPanel = config_entry.runtime_data

    async_add_entities(
        ZWaveDimmer(
            QolsysPanel,
            dimmer.dimmer_node_id,
            config_entry.unique_id,
        )
        for dimmer in QolsysPanel.state.zwave_dimmers
    )

def to_qolsys_level(level):
    """Convert the given Home Assistant light level (0-255) to Qolsys (0-99)."""
    return int((level * 99) / 255)

def to_hass_level(level):
    """Convert the given Lutron (0-99) light level to Home Assistant (0-255)."""
    return int((level * 255) / 99)

class ZWaveDimmer(QolsysZwaveDimmerEntity, LightEntity):
    """A ZWave dimmer light entity."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_name = None

    def __init__(self, QolsysPanel: qolsys_controller, node_id: int, unique_id: str) -> None:
        """Initialise a ZWaveLightEntity."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = self._zwave_dimmer_unique_id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.QolsysPanel.plugin.connected and self._dimmer.node_status == 'Normal'

    async def async_turn_on(self, **kwargs:Any) -> None:
        """Turn device on."""
        brightness = -1
        if ATTR_BRIGHTNESS in kwargs:
            brightness = to_qolsys_level(kwargs[ATTR_BRIGHTNESS])

        await self.QolsysPanel.plugin.command_zwave_switch_multi_level(self._dimmer.dimmer_node_id,brightness)

    async def async_turn_off(self, **kwargs:Any) -> None:
        """Turn device off."""
        await self.QolsysPanel.plugin.command_zwave_switch_multi_level(self._dimmer.dimmer_node_id,0)

    @property
    def is_on(self) -> bool:
        """Return if the light is on."""
        return self._dimmer.is_on()

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        return to_hass_level(int(self._dimmer.dimmer_level))

