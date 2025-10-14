"""Support for Qolsys Z-Wave Thermostats."""

from __future__ import annotations

from typing import Any

from qolsys_controller import qolsys_controller
from qolsys_controller.enum_zwave import ThermostatFanMode, ThermostatMode

from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import (
    HVACMode,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysZwaveThermostatEntity
from .types import QolsysPanelConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Thermostats entities."""
    QolsysPanel = config_entry.runtime_data

    entities: list[QolsysZwaveThermostatEntity] = []

    for thermostat in QolsysPanel.state.zwave_thermostats:
        entities.append(
            ZWaveThermostat(QolsysPanel, thermostat.node_id, config_entry.unique_id)
        )

    async_add_entities(entities)


class ZWaveThermostat(QolsysZwaveThermostatEntity, ClimateEntity):
    """An Z-Wave Thermostat entity for a qolsys panel."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: int, unique_id: str
    ) -> None:
        """Initialise a Qolsys Z-Wave Thermostat entity."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = self._zwave_thermostat_unique_id
        self._attr_target_temperature_step = 1

        available_thermostat_modes = self._thermostat.available_thermostat_mode
        available_fan_modes = self._thermostat.available_thermostat_fan_mode

        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        
        # Add turn off attribute
        if ThermostatMode.OFF in available_thermostat_modes:
            self._attr_supported_features = self._attr_supported_features | ClimateEntityFeature.TURN_OFF

        # Add fan attribute
        if available_fan_modes != 0:
            self._attr_supported_features = self._attr_supported_features | ClimateEntityFeature.FAN_MODE

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.QolsysPanel.plugin.connected and self._thermostat.node_status == "Normal"

    @property
    def current_temperature(self) -> float:
        return float(self._thermostat.thermostat_current_temp)

    @property
    def target_temperature(self) -> float:
        return float(self._thermostat.thermostat_target_temp)

    @property
    def temperature_unit(self) -> str:
        panel_temp_unit = self._thermostat.thermostat_device_temp_unit

        if panel_temp_unit == "F":
            return UnitOfTemperature.FAHRENHEIT

        if panel_temp_unit == "C":
            return UnitOfTemperature.CELSIUS

        return None

    @property
    def fan_mode(self):
        qolsys_fan_mode = self._thermostat.thermostat_fan_mode
        return self._qolsys_to_hass_fan_mode(qolsys_fan_mode)

    @property
    def fan_modes(self):
        hass_fan_modes:list = []
        qolsys_fan_modes:list[ThermostatFanMode] = self._thermostat.available_thermostat_fan_mode
        for qolsys_fan_mode in qolsys_fan_modes:
            fan_mode = self._qolsys_to_hass_fan_mode(qolsys_fan_mode)
            if fan_mode not in hass_fan_modes and fan_mode is not None:
                hass_fan_modes.append(fan_mode)

        return hass_fan_modes

    @property
    def hvac_action(self):
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        qolsys_thermostat_mode:ThermostatMode = self._thermostat.thermostat_mode
        return self._qolsys_to_hass_thermostat_mode(qolsys_thermostat_mode)

    @property
    def hvac_modes(self):
        hass_hvac_modes:list[HVACMode] = []
        qolsys_thermostat_modes:list[ThermostatMode] = self._thermostat.available_thermostat_mode
        for qolsys_mode in qolsys_thermostat_modes:
            hvac_mode = self._qolsys_to_hass_thermostat_mode(qolsys_mode)
            if hvac_mode not in hass_hvac_modes and hvac_mode is not None:
                hass_hvac_modes.append(hvac_mode)

        return hass_hvac_modes

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        node_id = int(self._thermostat.thermostat_node_id)
        qolsys_thermostat_mode = self._hass_to_qolsys_thermostat_mode(hvac_mode)
        await self.QolsysPanel.plugin.command_zwave_thermostat_mode_set(node_id=node_id,mode=qolsys_thermostat_mode)

    async def async_turn_off(self):
        """Turn the entity off."""
        node_id = int(self._thermostat.thermostat_node_id)
        await self.QolsysPanel.plugin.command_zwave_thermostat_mode_set(node_id=node_id,mode=ThermostatMode.OFF)

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        node_id = int(self._thermostat.thermostat_node_id)
        qolsys_fan_mode = self._hass_to_qolsys_fan_mode(fan_mode)
        await self.QolsysPanel.plugin.command_zwave_thermostat_fan_mode_set(node_id=node_id,fan_mode=qolsys_fan_mode)

    async def async_set_temperature(self, **kwargs: Any):
        """Set new target temperature."""
        node_id = int(self._thermostat.thermostat_node_id)
        if value := kwargs.get(ATTR_TARGET_TEMP_HIGH):
            temp = int(value)
            await self.QolsysPanel.plugin.command_zwave_thermostat_setpoint_set(node_id=node_id,mode=ThermostatMode.HEAT,setpoint=temp)
        
        if value := kwargs.get(ATTR_TARGET_TEMP_LOW):
            temp = int(value)
            await self.QolsysPanel.plugin.command_zwave_thermostat_setpoint_set(node_id=node_id,mode=ThermostatMode.COOL,setpoint=temp)

        if value := kwargs.get(ATTR_TEMPERATURE):
            temp = int(value)
            current_thermosat_mode = self._qolsys_to_hass_thermostat_mode(self._thermostat.thermostat_mode)
            await self.QolsysPanel.plugin.command_zwave_thermostat_setpoint_set(node_id=node_id,mode=current_thermosat_mode,setpoint=temp)

    def _qolsys_to_hass_fan_mode(self,qolsys_fan_mode:ThermostatFanMode):
        match qolsys_fan_mode:
            case ThermostatFanMode.LOW:
                return FAN_LOW
            
            case ThermostatFanMode.AUTO_LOW:
                return FAN_AUTO
            
            case ThermostatFanMode.AUTO_HIGH:
                return FAN_AUTO
            
            case ThermostatFanMode.HIGH:
                return FAN_HIGH
            
            case ThermostatFanMode.AUTO_MEDIUM:
                return FAN_AUTO
            
            case ThermostatFanMode.MEDIUM:
                return FAN_MEDIUM
            
            case ThermostatFanMode.CIRCULATION:
                return FAN_AUTO
            
            case ThermostatFanMode.HUMIDITY_CIRCULATION:
                return FAN_AUTO
            
            case ThermostatFanMode.LEFT_RIGHT:
                return FAN_AUTO
            
            case ThermostatFanMode.QUIET:
                return FAN_LOW
            
            case ThermostatFanMode.EXTERNAL_CIRCULATION:
                return FAN_AUTO

            case ThermostatFanMode.MANUFACTURER_SPECEFIC:
                return FAN_AUTO

        return None

    def _qolsys_to_hass_thermostat_mode(self,qolsys_thermostat_mode:ThermostatMode) -> HVACMode:
                
        match qolsys_thermostat_mode:
            case ThermostatMode.OFF:
                return HVACMode.OFF
            
            case ThermostatMode.HEAT:
                return HVACMode.HEAT
            
            case ThermostatMode.FURNACE:
                return HVACMode.HEAT
            
            case ThermostatMode.AUX_HEAT:
                return HVACMode.HEAT
            
            case ThermostatMode.ENERGY_SAVE_HEAT:
                return HVACMode.HEAT
            
            case ThermostatMode.COOL:
                return HVACMode.COOL
            
            case ThermostatMode.ENERGY_SAVE_COOL:
                return HVACMode.COOL

            case ThermostatMode.AUTO:
                   return HVACMode.AUTO
            
            case ThermostatMode.AWAY:
                return HVACMode.AUTO
            
            case ThermostatMode.FULL_POWER:
                return HVACMode.AUTO
            
            case ThermostatMode.MOIST_AIR:
                return HVACMode.AUTO
            
            case ThermostatMode.RESUME:
                return HVACMode.AUTO
            
            case ThermostatMode.MANUFACTURER_SPECEFIC:
                return HVACMode.AUTO
                                            
            case ThermostatMode.FAN_ONLY:
                return HVACMode.FAN_ONLY
            
            case ThermostatMode.DRY_AIR:
                return HVACMode.DRY
            
            case ThermostatMode.AUTO_CHANGEOVER:
                return HVACMode.HEAT_COOL
            
        return None
    
    def _hass_to_qolsys_thermostat_mode(self,hass_hvac_mode:HVACMode) -> HVACMode:
        match hass_hvac_mode:
            case HVACMode.OFF:
                return ThermostatMode.OFF
            
            case HVACMode.HEAT:
                return ThermostatMode.HEAT
            
            case HVACMode.COOL:
                return ThermostatMode.COOL
            
            case HVACMode.HEAT_COOL:
                return ThermostatMode.AUTO_CHANGEOVER

            case HVACMode.AUTO:
                return ThermostatMode.AUTO
            
            case HVACMode.FAN_ONLY:
                return ThermostatMode.FAN_ONLY
            
            case HVACMode.DRY:
                return ThermostatMode.AUTO
            
        return None
    

    def _hass_to_qolsys_fan_mode(self,hass_fan_mode:str):
        
        if hass_fan_mode == FAN_AUTO:
            return ThermostatFanMode.AUTO_MEDIUM
        
        match hass_fan_mode:
            case "auto":
                return ThermostatFanMode.AUTO_MEDIUM
            
            case "high":
                return ThermostatFanMode.HIGH
            
            case "low":
                return ThermostatFanMode.LOW

        return ThermostatFanMode.AUTO_MEDIUM
