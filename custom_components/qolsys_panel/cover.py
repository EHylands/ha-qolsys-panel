"""Support for Qolsys Cover."""

from __future__ import annotations

import logging
from typing import Any

from qolsys_controller import qolsys_controller
from qolsys_controller.automation.service_cover import CoverService

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysAutomationDeviceEntity
from .types import QolsysPanelConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Covers."""
    QolsysPanel = config_entry.runtime_data
    unique_id = config_entry.unique_id
    assert unique_id is not None
    entities: list[CoverEntity] = []

    # Add Automation Device Covers
    for device in QolsysPanel.state.automation_devices:
        for service in device.service_get_protocol(CoverService):  # type: ignore[type-abstract]
            entities.append(
                AutomationDevice_Cover(
                    QolsysPanel,
                    device.virtual_node_id,
                    service.endpoint,
                    unique_id,
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
        cover = self._autdev.service_get(CoverService, endpoint)  # type: ignore[type-abstract]
        assert cover is not None
        self._cover: CoverService = cover
        self._attr_name = f"GarageDoor{'' if endpoint == 0 else endpoint} - {self._cover.automation_device.device_name}"

        self._attr_supported_features = CoverEntityFeature(0)
        if self._cover.supports_open():
            self._attr_supported_features |= CoverEntityFeature.OPEN

        if self._cover.supports_close():
            self._attr_supported_features |= CoverEntityFeature.CLOSE

        if self._cover.supports_stop():
            self._attr_supported_features |= CoverEntityFeature.STOP

        if self._cover.supports_position():
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._cover.open()

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._cover.close()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        position = kwargs.get(ATTR_POSITION)
        if position is not None:
            await self._cover.set_current_position(position)

    @property
    def is_closed(self) -> bool | None:
        return self._cover.is_closed

    @property
    def is_closing(self) -> bool | None:
        return self._cover.is_closing

    @property
    def is_opening(self) -> bool | None:
        return self._cover.is_opening
