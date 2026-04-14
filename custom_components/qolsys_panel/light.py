"""Support for Qolsys Lights."""

from __future__ import annotations


from typing import Any

from qolsys_controller import qolsys_controller
from qolsys_controller.automation.service_light import LightService

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


from .types import QolsysPanelConfigEntry
from .entity import QolsysAutomationDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    QolsysPanel = config_entry.runtime_data
    entities: list[LightEntity] = []

    # Add Automation Device Lights
    for device in QolsysPanel.state.automation_devices:
        for service in device.service_get_protocol(LightService):
            entities.append(
                AutomationDevice_Light(
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


class AutomationDevice_Light(QolsysAutomationDeviceEntity, LightEntity):
    """Automation Device Light Entity."""

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

        if self._service.supports_level():
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
