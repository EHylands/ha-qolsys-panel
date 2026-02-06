"""Support for Qolsys Z-Wave Dimmer."""

from __future__ import annotations

import logging

from typing import Any

from qolsys_controller import qolsys_controller
from qolsys_controller.enum_zwave import ZwaveDeviceClass
from qolsys_controller.enum_adc import vdFuncState
from qolsys_controller.protocol_zwave.dimmer import QolsysDimmer
from qolsys_controller.protocol_adc.service_light import QolsysAdcLightService
from qolsys_controller.automation.service_light import LightService

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


from .types import QolsysPanelConfigEntry
from .entity import QolsysAutomationDeviceEntity, QolsysZwaveEntity
from .entity_adc import QolsysAdcEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ligh for each Z-Wave dimmer."""
    QolsysPanel = config_entry.runtime_data
    entities: list[QolsysZwaveEntity] = []

    # Add Z-Wave dimmers
    for dimmer in QolsysPanel.state.zwave_dimmers:
        entities.append(
            ZwaveDimmer(QolsysPanel, dimmer.dimmer_node_id, config_entry.unique_id)
        )

    # Add Virtual ADC Lights
    for adc_device in QolsysPanel.state.adc_devices:
        for service in adc_device.services:
            if isinstance(service, QolsysAdcLightService):
                entities.append(
                    AdcLight(
                        QolsysPanel,
                        adc_device.device_id,
                        service.id,
                        config_entry.unique_id,
                    )
                )

    # Add Automation Device Lights
    for device in QolsysPanel.state.automation_devices:
        for service in device.service_get_protocol(LightService):
            entities.append(
                AutomationDeviceLight(
                    QolsysPanel,
                    device.virtual_node_id,
                    service.endpoint,
                    config_entry.unique_id,
                )
            )

    async_add_entities(entities)


def to_qolsys_level(level):
    """Convert the given Home Assistant light level (0-255) to Qolsys (0-99)."""
    return int((level * 99) / 255)


def to_hass_level(level):
    """Convert the given Qolsys (0-99) light level to Home Assistant (0-255)."""
    return int((level * 255) / 99)


class AdcLight(QolsysAdcEntity, LightEntity):
    """ADC Light entity"""

    _attr_name = None
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        device_id: str,
        service_id: int,
        unique_id: str,
    ) -> None:
        super().__init__(QolsysPanel, device_id, unique_id)
        self._attr_unique_id = f"{self._adc_unique_id}_light_{service_id}"
        self._service_id = service_id

    @property
    def is_on(self) -> bool:
        light_service = self._device.get_adc_service(self._service_id)
        if isinstance(light_service, QolsysAdcLightService):
            return light_service.is_on()

        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.QolsysPanel.command_panel_virtual_device_action(
            self._device_id, self._service_id, vdFuncState.ON
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.QolsysPanel.command_panel_virtual_device_action(
            self._device_id, self._service_id, vdFuncState.OFF
        )


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
                self._node.node_id, "0", True
            )
        else:
            await self.QolsysPanel.command_zwave_switch_multilevel_set(
                self._node.node_id, "0", brightness
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        if self._node.generic_device_type in (
            ZwaveDeviceClass.SwitchBinary,
            ZwaveDeviceClass.RemoteSwitchBinary,
        ):
            await self.QolsysPanel.command_zwave_switch_binary_set(
                self._node.node_id, "0", False
            )
        else:
            await self.QolsysPanel.command_zwave_switch_multilevel_set(
                self._node.node_id, "0", 0
            )

    @property
    def is_on(self) -> bool:
        """Return if the light is on."""
        return self._node.is_on()

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        return to_hass_level(int(self._node.dimmer_level))


class AutomationDeviceLight(QolsysAutomationDeviceEntity, LightEntity):
    """Automation Device light entity."""

    _attr_name = None

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        virtual_node_id: str,
        endpoint: int,
        unique_id: str,
    ) -> None:
        super().__init__(QolsysPanel, virtual_node_id, unique_id)
        self._attr_unique_id = f"{self._autdev_unique_id}_light{endpoint}"
        self._service = self._autdev.service_get(LightService, endpoint)

        self._attr_name = f"Light{'' if endpoint == 0 else endpoint} - {self._service.automation_device.device_name}"

        if self._service.is_level_supported():
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            brightness = to_qolsys_level(kwargs[ATTR_BRIGHTNESS])
            await self._service.set_level(brightness)
            return

        await self._service.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._service.turn_off()

    @property
    def is_on(self) -> bool:
        return self._service.is_on

    @property
    def brightness(self) -> int | None:
        return to_hass_level(self._service.level)
