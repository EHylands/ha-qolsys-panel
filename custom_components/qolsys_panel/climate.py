"""Support for Qolsys Thermostats."""

from __future__ import annotations

import logging
from typing import Any

from qolsys_controller import qolsys_controller
from qolsys_controller.enum_qolsys import QolsysTemperatureUnit, QolsysHvacMode
from qolsys_controller.automation.service_thermostat import ThermostatService

from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import (
    HVACMode,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from custom_components.qolsys_panel.entity import QolsysAutomationDeviceEntity

from .types import QolsysPanelConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Thermostats entities."""
    QolsysPanel = config_entry.runtime_data
    entities: list[ClimateEntity] = []

    # Add Automation Device Thermostats
    for device in QolsysPanel.state.automation_devices:
        for service in device.service_get_protocol(ThermostatService):
            entities.append(
                AutomationDevice_Climate(
                    QolsysPanel,
                    device.virtual_node_id,
                    service.endpoint,
                    config_entry.unique_id,
                )
            )

    async_add_entities(entities)


class AutomationDevice_Climate(QolsysAutomationDeviceEntity, ClimateEntity):
    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        virtual_node_id: str,
        endpoint: int,
        unique_id: str,
    ) -> None:
        super().__init__(QolsysPanel, virtual_node_id, unique_id)
        self._attr_unique_id = f"{self._autdev_unique_id}_thermostat{endpoint}"
        self._service = self._autdev.service_get(ThermostatService, endpoint)
        self._attr_name = f"Thermostat{'' if endpoint == 0 else endpoint} - {self._service.automation_device.device_name}"
        self._attr_target_temperature_step = self._service.target_temperature_step

        self._attr_supported_features = 0
        if self._service.supports_target_temperature():
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

        if self._service.supports_target_temperature_range():
            self._attr_supported_features |= (
                ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            )

        if self._service.supports_fan_mode():
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        if self._service.supports_turn_off():
            self._attr_supported_features |= ClimateEntityFeature.TURN_OFF

    @property
    def current_temperature(self) -> float:
        return self._service.current_temperature

    @property
    def current_humidity(self) -> float | None:
        return self._service.current_humidity

    @property
    def target_temperature(self) -> float | None:
        # In AUTO mode, return None so dual sliders appear
        if self._service.hvac_mode in (QolsysHvacMode.AUTO, QolsysHvacMode.HEAT_COOL):
            return None

        # In OFF mode, return None (no slider needed)
        if self._service.hvac_mode == QolsysHvacMode.OFF:
            return None

        # For HEAT mode, return heat setpoint
        if self._service.hvac_mode == QolsysHvacMode.HEAT:
            return self._service.target_heat_temp

        # For COOL mode, return cool setpoint
        if self._service.hvac_mode == QolsysHvacMode.COOL:
            return self._service.target_cool_temp

        # Default: no slider
        return None

    @property
    def temperature_unit(self) -> str:
        if self._service.device_temperature_unit == QolsysTemperatureUnit.CELSIUS:
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

    @property
    def target_temperature_high(self) -> float | None:
        if self._service.hvac_mode in (QolsysHvacMode.AUTO, QolsysHvacMode.HEAT_COOL):
            return self._service.target_cool_temp
        return None

    @property
    def target_temperature_low(self) -> float | None:
        if self._service.hvac_mode in (QolsysHvacMode.AUTO, QolsysHvacMode.HEAT_COOL):
            return self._service.target_heat_temp
        return None

    @property
    def fan_mode(self):
        return self._service.fan_mode

    @property
    def fan_modes(self) -> list[str]:
        return self._service.fan_modes

    @property
    def hvac_action(self):
        return self._service.hvac_action

    @property
    def hvac_mode(self) -> HVACMode:
        return self._service.hvac_mode

    @property
    def hvac_modes(self):
        return self._service.hvac_modes

    @property
    def min_temp(self) -> float:
        return self._service.min_temp

    @property
    def max_temp(self) -> float:
        return self._service.max_temp

    async def async_set_hvac_mode(self, hvac_mode):
        await self._service.set_hvac_mode(hvac_mode)

    async def async_turn_off(self):
        await self._service.turn_off()

    async def async_set_fan_mode(self, fan_mode):
        await self._service.set_fan_mode(fan_mode)

    async def async_set_temperature(self, **kwargs: Any):
        if value := kwargs.get(ATTR_TARGET_TEMP_HIGH):
            await self._service.set_temperature(value, QolsysHvacMode.COOL)

        if value := kwargs.get(ATTR_TARGET_TEMP_LOW):
            await self._service.set_temperature(value, QolsysHvacMode.HEAT)

        if value := kwargs.get(ATTR_TEMPERATURE):
            await self._service.set_temperature(value, self._service.hvac_mode)
