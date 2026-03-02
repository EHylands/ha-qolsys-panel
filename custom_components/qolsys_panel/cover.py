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

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .types import QolsysPanelConfigEntry
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

    # Add Automation Device Covers
    for device in QolsysPanel.state.automation_devices:
        for service in device.service_get_protocol(CoverService):
            entities.append(
                AutomationDevice_Cover(
                    QolsysPanel,
                    device.virtual_node_id,
                    service.endpoint,
                    config_entry.unique_id,
                )
            )

    async_add_entities(entities)


class AutomationDevice_Cover(QolsysAutomationDeviceEntity, CoverEntity):
    """Automation Device Garage Door Cover Entity"""

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

        self._attr_supported_features = 0
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
        return self._cover.is_closed
