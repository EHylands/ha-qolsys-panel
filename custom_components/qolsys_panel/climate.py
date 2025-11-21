"""Support for Qolsys Z-Wave Thermostats."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from qolsys_controller import qolsys_controller
from qolsys_controller.enum_zwave import ThermostatFanMode, ThermostatMode

from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import (
    HVACMode,
    FAN_AUTO,
    FAN_ON,
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

_LOGGER = logging.getLogger(__name__)


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
    """A Z-Wave Thermostat entity for a qolsys panel."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: str, unique_id: str
    ) -> None:
        """Initialise a Qolsys Z-Wave Thermostat entity."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = self._zwave_thermostat_unique_id
        self._attr_target_temperature_step = 1

        available_thermostat_modes = self._thermostat.available_thermostat_mode()
        available_fan_modes = self._thermostat.available_thermostat_fan_mode()

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        )
        self._last_sent_mode = (
            None  # Track last commanded mode (panel doesn't send updates)
        )

        # Add turn off attribute
        if ThermostatMode.OFF in available_thermostat_modes:
            self._attr_supported_features = (
                self._attr_supported_features | ClimateEntityFeature.TURN_OFF
            )

        # Add fan attribute
        if available_fan_modes != 0:
            self._attr_supported_features = (
                self._attr_supported_features | ClimateEntityFeature.FAN_MODE
            )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.QolsysPanel.connected and self._thermostat.node_status == "Normal"

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return float(self._thermostat.thermostat_current_temp)

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature (mode-aware)."""
        # Use tracked mode instead of panel mode (panel doesn't send state updates)
        mode = self.hvac_mode

        # In AUTO mode, return None so dual sliders appear
        if mode == HVACMode.AUTO:
            return None

        # In OFF mode, return None (no slider needed)
        if mode == HVACMode.OFF:
            return None

        # For HEAT mode, return heat setpoint
        if mode == HVACMode.HEAT:
            temp = self._thermostat.thermostat_target_heat_temp
            try:
                return float(temp) if temp else 72.0
            except (ValueError, TypeError):
                _LOGGER.warning(
                    f"Invalid heat temperature value '{temp}', using default 72.0"
                )
                return 72.0

        # For COOL mode, return cool setpoint
        if mode == HVACMode.COOL:
            temp = self._thermostat.thermostat_target_cool_temp
            try:
                return float(temp) if temp else 72.0
            except (ValueError, TypeError):
                _LOGGER.warning(
                    f"Invalid cool temperature value '{temp}', using default 72.0"
                )
                return 72.0

        # Default: no slider
        return None

    @property
    def temperature_unit(self) -> str:
        """Return the temperature unit."""
        panel_temp_unit = self._thermostat.thermostat_device_temp_unit

        if panel_temp_unit == "F":
            return UnitOfTemperature.FAHRENHEIT

        if panel_temp_unit == "C":
            return UnitOfTemperature.CELSIUS

    @property
    def target_temperature_high(self) -> float | None:
        """Return the upper target temperature for AUTO mode."""
        # Only return a value in AUTO mode
        if self.hvac_mode != HVACMode.AUTO:
            return None

        try:
            temp = self._thermostat.thermostat_target_cool_temp
            return float(temp) if temp else 74.0
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Invalid cool temperature value in AUTO mode, using default 74.0"
            )
            return 74.0

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lower target temperature for AUTO mode."""
        # Only return a value in AUTO mode
        if self.hvac_mode != HVACMode.AUTO:
            return None

        try:
            temp = self._thermostat.thermostat_target_heat_temp
            return float(temp) if temp else 68.0
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Invalid heat temperature value in AUTO mode, using default 68.0"
            )
            return 68.0

    @property
    def fan_mode(self):
        """Return the fan mode."""
        qolsys_fan_mode = self._thermostat.thermostat_fan_mode
        return self._qolsys_to_hass_fan_mode(qolsys_fan_mode)

    @property
    def fan_modes(self):
        """Return available fan modes."""
        hass_fan_modes: list = []
        qolsys_fan_modes: list[ThermostatFanMode] = (
            self._thermostat.available_thermostat_fan_mode()
        )
        for qolsys_fan_mode in qolsys_fan_modes:
            fan_mode = self._qolsys_to_hass_fan_mode(qolsys_fan_mode)
            if fan_mode not in hass_fan_modes and fan_mode is not None:
                hass_fan_modes.append(fan_mode)

        return hass_fan_modes

    @property
    def hvac_action(self):
        """Return current HVAC action."""
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        # Return tracked mode if we have one (panel doesn't send updates)
        if self._last_sent_mode is not None:
            return self._last_sent_mode

        qolsys_thermostat_mode = self._thermostat.thermostat_mode
        return self._qolsys_to_hass_thermostat_mode(qolsys_thermostat_mode)

    @property
    def hvac_modes(self):
        """Return available HVAC modes."""
        hass_hvac_modes: list[HVACMode] = []
        qolsys_thermostat_modes: list[ThermostatMode] = (
            self._thermostat.available_thermostat_mode()
        )
        for qolsys_mode in qolsys_thermostat_modes:
            hvac_mode = self._qolsys_to_hass_thermostat_mode(qolsys_mode)
            if hvac_mode not in hass_hvac_modes and hvac_mode is not None:
                hass_hvac_modes.append(hvac_mode)

        return hass_hvac_modes

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        _LOGGER.debug(
            f"Setting HVAC mode to {hvac_mode} (node_id: {self._thermostat.thermostat_node_id})"
        )

        # Update mode tracking FIRST (before await that might hang)
        # This provides optimistic UI update since panel doesn't send state changes
        self._last_sent_mode = hvac_mode
        self.async_write_ha_state()

        # Then send the command (await might hang, but UI is already updated)
        qolsys_thermostat_mode = self._hass_to_qolsys_thermostat_mode(hvac_mode)

        try:
            await self.QolsysPanel.command_zwave_thermostat_mode_set(
                node_id=self._thermostat.thermostat_node_id, mode=qolsys_thermostat_mode
            )
            _LOGGER.debug(f"HVAC mode set to {hvac_mode} successfully")
        except Exception as e:
            _LOGGER.error(f"Failed to set HVAC mode to {hvac_mode}: {e}")
            # Mode already updated optimistically above, keep it for now
            # Panel state will eventually reconcile or user will notice and retry

    async def async_turn_off(self):
        """Turn the entity off."""
        await self.QolsysPanel.command_zwave_thermostat_mode_set(
            node_id=self._thermostat.thermostat_node_id, mode=ThermostatMode.OFF
        )

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        qolsys_fan_mode = self._hass_to_qolsys_fan_mode(fan_mode)
        await self.QolsysPanel.command_zwave_thermostat_fan_mode_set(
            node_id=self._thermostat.thermostat_node_id, fan_mode=qolsys_fan_mode
        )

    def _handle_setpoint_error(self, task: asyncio.Task, mode_name: str):
        """Handle errors from setpoint command tasks."""
        try:
            task.result()  # Raises exception if task failed
        except Exception as e:
            _LOGGER.error(f"Failed to set {mode_name} setpoint: {e}")

    async def async_set_temperature(self, **kwargs: Any):
        """Set new target temperature."""
        _LOGGER.debug(f"Setting temperature with kwargs: {kwargs}")
        node_id = self._thermostat.thermostat_node_id

        # Handle dual slider mode (AUTO mode - both high and low)
        if value := kwargs.get(ATTR_TARGET_TEMP_HIGH):
            temp = int(value)
            _LOGGER.debug(f"Setting COOL setpoint to {temp} (node_id: {node_id})")
            # Fire-and-forget to avoid blocking (panel might sleep)
            # Add error callback to log failures
            task = asyncio.create_task(
                self.QolsysPanel.command_zwave_thermostat_setpoint_set(
                    node_id=node_id, mode=ThermostatMode.COOL, setpoint=temp
                )
            )
            task.add_done_callback(lambda t: self._handle_setpoint_error(t, "COOL"))

        if value := kwargs.get(ATTR_TARGET_TEMP_LOW):
            temp = int(value)
            _LOGGER.debug(f"Setting HEAT setpoint to {temp} (node_id: {node_id})")
            # Fire-and-forget to avoid blocking (panel might sleep)
            # Add error callback to log failures
            task = asyncio.create_task(
                self.QolsysPanel.command_zwave_thermostat_setpoint_set(
                    node_id=node_id, mode=ThermostatMode.HEAT, setpoint=temp
                )
            )
            task.add_done_callback(lambda t: self._handle_setpoint_error(t, "HEAT"))

        # Handle single slider mode (HEAT or COOL mode)
        if value := kwargs.get(ATTR_TEMPERATURE):
            temp = int(value)
            current_thermostat_mode = self.hvac_mode
            if current_thermostat_mode is None:
                current_thermostat_mode = ThermostatMode.HEAT

            _LOGGER.debug(
                f"Setting {current_thermostat_mode} setpoint to {temp} (node_id: {node_id})"
            )
            await self.QolsysPanel.command_zwave_thermostat_setpoint_set(
                node_id=node_id, mode=current_thermostat_mode, setpoint=temp
            )

    def _qolsys_to_hass_fan_mode(self, qolsys_fan_mode: ThermostatFanMode):
        """Convert Qolsys fan mode to Home Assistant fan mode."""
        match qolsys_fan_mode:
            case ThermostatFanMode.LOW:
                return FAN_ON

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

    def _qolsys_to_hass_thermostat_mode(
        self, qolsys_thermostat_mode: ThermostatMode
    ) -> HVACMode:
        """Convert Qolsys thermostat mode to Home Assistant HVAC mode."""
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

    def _hass_to_qolsys_thermostat_mode(self, hass_hvac_mode: HVACMode) -> HVACMode:
        """Convert Home Assistant HVAC mode to Qolsys thermostat mode."""
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

        return None

    def _hass_to_qolsys_fan_mode(self, hass_fan_mode: str):
        """Convert Home Assistant fan mode to Qolsys fan mode."""
        if hass_fan_mode == FAN_AUTO:
            return ThermostatFanMode.AUTO_LOW

        if hass_fan_mode == FAN_ON:
            return ThermostatFanMode.LOW

        match hass_fan_mode:
            case "auto":
                return ThermostatFanMode.AUTO_LOW

            case "on":
                return ThermostatFanMode.LOW

            case "high":
                return ThermostatFanMode.HIGH

            case "low":
                return ThermostatFanMode.LOW

        return ThermostatFanMode.AUTO_LOW
