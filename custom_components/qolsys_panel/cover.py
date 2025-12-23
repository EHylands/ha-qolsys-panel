"""Support for Qolsys Cover."""

from __future__ import annotations

import logging
from homeassistant.exceptions import HomeAssistantError

from homeassistant.components.cover import (
    CoverEntity,
    CoverDeviceClass,
    CoverEntityFeature,
)

from qolsys_controller import qolsys_controller
from qolsys_controller.adc_service_garagedoor import QolsysAdcGarageDoorService

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .types import QolsysPanelConfigEntry
from .entity_adc import QolsysAdcEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Covers."""
    QolsysPanel = config_entry.runtime_data

    entities: list[CoverEntity] = []

    # Add Virtual ADC Garage Door
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

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        HomeAssistantError("Not Implemented")

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        HomeAssistantError("Not Implemented")
