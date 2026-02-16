"""Support for Qolsys Cover."""

from __future__ import annotations

import logging

from homeassistant.components.cover import (
    CoverEntity,
    CoverDeviceClass,
    CoverEntityFeature,
)

from qolsys_controller import qolsys_controller
from qolsys_controller.automation.service_cover import CoverService
from qolsys_controller.protocol_adc.service_garagedoor import QolsysAdcGarageDoorService
from qolsys_controller.enum_adc import vdFuncState

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from custom_components.qolsys_panel.entity import QolsysZwaveEntity

from .types import QolsysPanelConfigEntry
from .entity_adc import QolsysAdcEntity
from .entity import QolsysAutomationDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Covers."""
    QolsysPanel = config_entry.runtime_data

    entities: list[CoverEntity] = []

    # Add Virtual ADC Garage Door - Legacy
    for adc_device in QolsysPanel.state.adc_devices:
        for service in adc_device.services:
            if isinstance(service, QolsysAdcGarageDoorService):
                entities.append(
                    AdcGarageDoor(
                        QolsysPanel,
                        adc_device.device_id,
                        service.id,
                        config_entry.unique_id,
                    )
                )
    # Add Z-Wave Garage Doors - Legacy
    for garage_door in QolsysPanel.state.zwave_garage_doors:
        entities.append(
            ZwaveDevice_GarageDoor(
                QolsysPanel, garage_door.node_id, config_entry.unique_id
            )
        )
    # Add Automation Device Covers
    for device in QolsysPanel.state.automation_devices(CoverService):
            entities.append(
                AutomationDeviceCover(
                    QolsysPanel,
                    device.virtual_node_id,
                    service.endpoint,
                    config_entry.unique_id,
                )
            )

    async_add_entities(entities)


class AdcGarageDoor(QolsysAdcEntity, CoverEntity):
    """ADC Garage Door Cover entity"""

    _attr_name = None
    _attr_supported_features = CoverEntityFeature.CLOSE | CoverEntityFeature.OPEN

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        device_id: str,
        service_id: int,
        unique_id: str,
    ) -> None:
        """Initialise a AdcGarageDoor."""
        super().__init__(QolsysPanel, device_id, unique_id)
        self._attr_unique_id = f"{self._adc_unique_id}_garagedoor_{service_id}"
        self._service_id = service_id
        self.device_class = CoverDeviceClass.GARAGE
        self._value_is_closing = False
        self._value_is_opening = False

    @property
    def is_closing(self) -> bool:
        return self._value_is_closing

    @property
    def is_openning(self) -> bool:
        return self._value_is_opening

    async def async_open_cover(self, **kwargs):
        self._value_is_opening = True
        self._vaue_is_closing = False
        self.async_schedule_update_ha_state()
        await self.QolsysPanel.command_panel_virtual_device_action(
            self._device_id, self._service_id, vdFuncState.ON
        )
        self._value_is_opening = False

    async def async_close_cover(self, **kwargs):
        self._value_is_closing = True
        self._value_is_opening = False
        self.async_schedule_update_ha_state()
        await self.QolsysPanel.command_panel_virtual_device_action(
            self._device_id, self._service_id, vdFuncState.OFF
        )
        self._value_is_closing = False

    @property
    def is_closed(self) -> bool | None:
        service: QolsysAdcGarageDoorService = self._device.get_adc_service(
            self._service_id
        )
        if isinstance(service, QolsysAdcGarageDoorService):
            return service.is_closed()

        return None


class ZwaveDevice_GarageDoor(QolsysZwaveEntity, CoverEntity):
    """Z-Wave Garage Door Cover entity"""

    _attr_name = None

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        node_id: str,
        unique_id: str,
    ) -> None:
        """Initialise a Z-Wace GarageDoor."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = f"{self._zwave_unique_id}_garagedoor"
        self.device_class = CoverDeviceClass.GARAGE

        # if ZwaveCommandClass.BarrierOperator:
        self._attr_supported_features |= (
            CoverEntityFeature.CLOSE | CoverEntityFeature.OPEN
        )

    async def async_open_cover(self, **kwargs):
        _LOGGER.debug("Open - Available Commands: %s", self._node.command_class_list)

    async def async_close_cover(self, **kwargs):
        _LOGGER.debug("Close - Available Commands: %s", self._node.command_class_list)

    @property
    def is_closed(self) -> bool | None:
        return None


class AutomationDeviceCover(QolsysAutomationDeviceEntity, CoverEntity):
    """Automation Device Garage Door Cover entity"""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        virtual_node_id: str,
        endpoint: int,
        unique_id: str,
    ) -> None:
        super().__init__(QolsysPanel, virtual_node_id, unique_id)
        self._attr_unique_id = f"{self._autdev_unique_id}_cover{endpoint}"
        self.device_class = CoverDeviceClass.GARAGE
        self._cover = self._autdev.service_get(CoverService, endpoint)
        self._attr_name = f"GarageDoor{'' if endpoint == 0 else endpoint} - {self._cover.automation_device.device_name}"

        if self._cover.supports_open():
            self._attr_supported_features |= CoverEntityFeature.OPEN

        if self._cover.supports_close():
            self._attr_supported_features |= CoverEntityFeature.CLOSE

        if self._cover.supports_stop():
            self._attr_supported_features |= CoverEntityFeature.STOP

        if self._cover.supports_position():
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION

    async def async_open_cover(self, **kwargs):
        await self._cover.open()

    async def async_close_cover(self, **kwargs):
        await self._cover.close()

    async def set_current_position(self, **kwargs):
        position = kwargs.get("position")
        if position is not None:
            await self._cover.set_position(position)

    @property
    def is_closed(self) -> bool | None:
        return self._cover.is_closed()
