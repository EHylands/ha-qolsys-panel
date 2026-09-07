from __future__ import annotations

import json
import logging
from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from ..automation.service import AutomationService
from ..enum_qolsys import (
    QolsysFanMode,
    QolsysHvacAction,
    QolsysHvacMode,
    QolsysNotification,
    QolsysTemperatureUnit,
)
from ..enum_zwave import (
    BITMASK_SUPPORTED_THERMOSTAT_FAN_MODE,
    BITMASK_SUPPORTED_THERMOSTAT_MODE,
    ThermostatFanMode,
    ThermostatMode,
)
from ..observable import Event

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice

LOGGER = logging.getLogger(__name__)


class ThermostatService(AutomationService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)
        self._service_name = "ThermostatService"
        self._hvac_mode: QolsysHvacMode | None = None
        self._hvac_modes: list[QolsysHvacMode] = []
        self._fan_mode: QolsysFanMode | None = None
        self._fan_modes: list[QolsysFanMode] = []
        self._hvac_action: QolsysHvacAction | None = None
        self._current_temperature: float | None = None
        self._current_humidity: float | None = None
        self._target_heat_temp: float | None = None
        self._target_cool_temp: float | None = None
        self._target_humidity: float | None = None
        self._target_temperature_step: float | None = None
        self._device_temperature_unit: QolsysTemperatureUnit | None = None

        self._min_temp_celsius = 7.0
        self._min_temp_fahrenheit = 45.0
        self._max_temp_celsius = 35.0
        self._max_temp_fahrenheit = 95.0

    @property
    def hvac_mode(self) -> QolsysHvacMode | None:
        return self._hvac_mode

    @hvac_mode.setter
    def hvac_mode(self, value: QolsysHvacMode | None) -> None:
        if self._hvac_mode != value:
            self._hvac_mode = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - hvac_mode: %s", self.prefix, value.name if value else None)

    @property
    def min_temp(self) -> float:
        if self.device_temperature_unit == QolsysTemperatureUnit.CELSIUS:
            return self._min_temp_celsius
        return self._min_temp_fahrenheit

    @property
    def max_temp(self) -> float:
        if self.device_temperature_unit == QolsysTemperatureUnit.CELSIUS:
            return self._max_temp_celsius
        return self._max_temp_fahrenheit

    @property
    def hvac_modes(self) -> list[QolsysHvacMode]:
        return self._hvac_modes

    @hvac_modes.setter
    def hvac_modes(self, value: list[QolsysHvacMode]) -> None:
        unique_hvac_modes = sorted(set(value), key=lambda mode: mode.name)

        if self._hvac_modes != unique_hvac_modes:
            self._hvac_modes = unique_hvac_modes
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - hvac_modes: %s", self.prefix, ",".join(mode.name for mode in self._hvac_modes))

    @property
    def hvac_action(self) -> QolsysHvacAction | None:
        if self.hvac_mode == QolsysHvacMode.OFF:
            return QolsysHvacAction.OFF

        if self.hvac_mode == QolsysHvacMode.FAN_ONLY:
            return QolsysHvacAction.FAN

        if self.hvac_mode == QolsysHvacMode.DRY:
            return QolsysHvacAction.DRYING

        if self.hvac_mode in (QolsysHvacMode.COOL, QolsysHvacMode.AUTO, QolsysHvacMode.HEAT_COOL):
            if self.current_temperature is not None and self.target_cool_temp is not None:
                if self.current_temperature > self.target_cool_temp:
                    return QolsysHvacAction.COOLING

        if self.hvac_mode in (QolsysHvacMode.HEAT, QolsysHvacMode.AUTO, QolsysHvacMode.HEAT_COOL):
            if self.current_temperature is not None and self.target_heat_temp is not None:
                if self.current_temperature < self.target_heat_temp:
                    return QolsysHvacAction.HEATING

        if self.supports_fan_mode() and self.fan_mode != QolsysFanMode.FAN_OFF:
            return QolsysHvacAction.FAN

        return QolsysHvacAction.IDLE

    @property
    def fan_mode(self) -> QolsysFanMode | None:
        return self._fan_mode

    @fan_mode.setter
    def fan_mode(self, value: QolsysFanMode | None) -> None:
        if self._fan_mode != value:
            self._fan_mode = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - fan_mode: %s", self.prefix, value.name if value else None)

    @property
    def fan_modes(self) -> list[QolsysFanMode]:
        return self._fan_modes

    @fan_modes.setter
    def fan_modes(self, value: list[QolsysFanMode]) -> None:
        unique_fan_modes = sorted(set(value), key=lambda mode: mode.name)

        if self._fan_modes != unique_fan_modes:
            self._fan_modes = unique_fan_modes
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - fan_modes: %s", self.prefix, ",".join(mode.name for mode in self._fan_modes))

    @property
    def current_temperature(self) -> float | None:
        return self._current_temperature

    @current_temperature.setter
    def current_temperature(self, value: float) -> None:
        if self._current_temperature != value:
            if self.device_temperature_unit == QolsysTemperatureUnit.FAHRENHEIT:
                if not self._min_temp_fahrenheit <= value <= self._max_temp_fahrenheit:
                    LOGGER.debug(
                        "%s - %s - temp %s°F out of range",
                        self.prefix,
                        self.service_name,
                        value,
                    )
                    return

            if self.device_temperature_unit == QolsysTemperatureUnit.CELSIUS:
                if not self._min_temp_celsius <= value <= self._max_temp_celsius:
                    LOGGER.debug(
                        "%s - %s - temp %s°C out of range",
                        self.prefix,
                        self.service_name,
                        value,
                    )
                    return

            self._current_temperature = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - current_temperature: %s", self.prefix, value)

    @property
    def current_humidity(self) -> float | None:
        return self._current_humidity

    @current_humidity.setter
    def current_humidity(self, value: float | None) -> None:
        if self._current_humidity != value:
            self._current_humidity = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - current_humidity: %s", self.prefix, value)

    @property
    def device_temperature_unit(self) -> QolsysTemperatureUnit | None:
        return self._device_temperature_unit

    @device_temperature_unit.setter
    def device_temperature_unit(self, value: QolsysTemperatureUnit) -> None:
        if self._device_temperature_unit != value:
            self._device_temperature_unit = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - device_temperature_unit: %s", self.prefix, value.name)

    @property
    def target_cool_temp(self) -> float | None:
        return self._target_cool_temp

    @target_cool_temp.setter
    def target_cool_temp(self, value: float) -> None:
        if self._target_cool_temp != value:
            self._target_cool_temp = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - target_cool_temp: %s", self.prefix, value)

    @property
    def target_heat_temp(self) -> float | None:
        return self._target_heat_temp

    @target_heat_temp.setter
    def target_heat_temp(self, value: float) -> None:
        if self._target_heat_temp != value:
            self._target_heat_temp = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - target_heat_temp: %s", self.prefix, value)

    @property
    def target_humidity(self) -> float | None:
        return self._target_humidity

    @property
    def target_temperature_step(self) -> float | None:
        return self._target_temperature_step

    @target_temperature_step.setter
    def target_temperature_step(self, value: float) -> None:
        if self._target_temperature_step != value:
            self._target_temperature_step = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - target_temperature_step: %s", self.prefix, value)

    @property
    def min_temperature(self) -> float | None:
        match self.device_temperature_unit:
            case QolsysTemperatureUnit.FAHRENHEIT:
                return self._min_temp_fahrenheit
            case QolsysTemperatureUnit.CELSIUS:
                return self._min_temp_celsius
            case _:
                return None

    @property
    def max_temperature(self) -> float | None:
        match self.device_temperature_unit:
            case QolsysTemperatureUnit.FAHRENHEIT:
                return self._max_temp_fahrenheit
            case QolsysTemperatureUnit.CELSIUS:
                return self._max_temp_celsius
            case _:
                return None

    @property
    def min_humidity(self) -> float | None:
        return None

    @property
    def max_humidity(self) -> float | None:
        return None

    @abstractmethod
    async def turn_on(self) -> None: ...

    @abstractmethod
    async def turn_off(self) -> None: ...

    @abstractmethod
    async def set_hvac_mode(self, hvac_mode: QolsysHvacMode) -> None: ...

    @abstractmethod
    async def set_fan_mode(self, fan_mode: QolsysFanMode) -> None: ...

    @abstractmethod
    async def set_humidity(self, humidity: float) -> None: ...

    @abstractmethod
    async def set_temperature(self, temperature: float, mode: QolsysHvacMode) -> None: ...

    def supports_target_temperature(self) -> bool:
        return QolsysHvacMode.COOL in self.hvac_modes or QolsysHvacMode.HEAT in self.hvac_modes

    def supports_target_temperature_range(self) -> bool:
        return QolsysHvacMode.HEAT_COOL in self.hvac_modes or QolsysHvacMode.AUTO in self.hvac_modes

    def supports_humidity(self) -> bool:
        return False

    def supports_fan_mode(self) -> bool:
        return self.fan_modes != []

    def supports_turn_on(self) -> bool:
        return False

    def supports_turn_off(self) -> bool:
        return QolsysHvacMode.OFF in self.hvac_modes

    def update_automation_service(self) -> None:
        try:
            dict = json.loads(self.automation_device.extras)
            self.current_temperature = float(dict.get("CURRENT_TEMP"))
            self.target_heat_temp = float(dict.get("TARGET_HEAT_TEMP"))
            self.target_cool_temp = float(dict.get("TARGET_COOL_TEMP"))
            self.device_temperature_unit = QolsysTemperatureUnit(dict.get("SET_DEVICE_TEMP_UNIT"))
            self._set_hvac_modes_from_bitmask(dict.get("THERMOSTAT_MODE_BIT_MASK", ""))
            self._set_fan_modes_from_bitmask(dict.get("FAN_MODE_BIT_MASK", ""))
            self._set_hvac_mode(dict.get("THERMOSTAT_MODE", ""))
            self._set_fan_mode(dict.get("FAN_MODE", ""))

            if self.device_temperature_unit == QolsysTemperatureUnit.CELSIUS:
                self.target_temperature_step = 0.5
            elif self.device_temperature_unit == QolsysTemperatureUnit.FAHRENHEIT:
                self.target_temperature_step = 1.0

        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
            LOGGER.error(
                "%s LightServiceZwave - update_automation_service - error parsing extras/status: %s / %s",
                self.prefix,
                self.automation_device.extras,
                self.automation_device.status,
            )

    def _set_hvac_mode(self, hvac_mode: str | int) -> None:
        LOGGER.debug("%s - hvac_mode: %s (%s)", self.prefix, hvac_mode, type(hvac_mode).__name__)

        if isinstance(hvac_mode, str):
            if hvac_mode == "":
                self.hvac_mode = QolsysHvacMode.AUTO
                return

            try:
                int_hvac_mode = int(hvac_mode.strip("[]"))
            except ValueError:
                LOGGER.error(
                    "%s - Invalid hvac_mode value: %r",
                    self.prefix,
                    hvac_mode,
                )
                return

        elif isinstance(hvac_mode, int):
            int_hvac_mode = hvac_mode

        else:
            LOGGER.error(
                "%s - Invalid hvac_mode type: %s (%r)",
                self.prefix,
                type(hvac_mode).__name__,
                hvac_mode,
            )
            return

        zwave_hvac_mode = ThermostatMode(int_hvac_mode)
        self.hvac_mode = self.ZWAVE_TO_QOLSYS_HVAC_MODE.get(zwave_hvac_mode, None)

    def _set_hvac_modes_from_bitmask(self, hvac_modes_bitmask: str) -> None:
        supported_hvac_modes: list[QolsysHvacMode] = []
        int_list = [int(x) for x in hvac_modes_bitmask.strip("[]").split(",") if x.strip()]
        bitmask = int.from_bytes(bytes(int_list), byteorder="little")
        for bit, mode in BITMASK_SUPPORTED_THERMOSTAT_MODE.items():
            if bitmask & (1 << bit):
                qolsys_thermostat_mode: QolsysHvacMode | None = self.ZWAVE_TO_QOLSYS_HVAC_MODE.get(mode)
                if qolsys_thermostat_mode:
                    supported_hvac_modes.append(qolsys_thermostat_mode)
        self.hvac_modes = supported_hvac_modes

    def _set_fan_mode(self, fan_mode: str) -> None:
        int_fan_mode = int(fan_mode.strip("[]"))
        zwave_fan_mode = ThermostatFanMode(int_fan_mode)
        self.fan_mode = self.ZWAVE_TO_QOLSYS_FAN_MODE.get(zwave_fan_mode, None)

    def _set_fan_modes_from_bitmask(self, fan_modes_bitmask: str) -> None:
        supported_fan_modes: list[QolsysFanMode] = []
        LOGGER.debug("fan modes string: %s", fan_modes_bitmask)

        int_list = []
        if isinstance(fan_modes_bitmask, list):
            int_list = [int(x) for x in fan_modes_bitmask]
        elif isinstance(fan_modes_bitmask, str):
            int_list = [int(x) for x in fan_modes_bitmask.strip("[]").split(",") if x.strip()]

        bitmask = int.from_bytes(bytes(int_list), byteorder="little")
        for bit, fan_mode in BITMASK_SUPPORTED_THERMOSTAT_FAN_MODE.items():
            if bitmask & (1 << bit):
                qolsys_fan_mode: QolsysFanMode | None = self.ZWAVE_TO_QOLSYS_FAN_MODE.get(fan_mode, None)
                if qolsys_fan_mode:
                    supported_fan_modes.append(qolsys_fan_mode)
        self.fan_modes = supported_fan_modes

    def info(self) -> list[str]:
        info_str = []
        info_str.append(f"{self.prefix} - hvac_mode: {self.hvac_mode.name if self.hvac_mode else None}")
        info_str.append(f"{self.prefix} - fan_mode: {self.fan_mode.name if self.fan_mode else None}")
        info_str.append(f"{self.prefix} - hvac_action: {self.hvac_action.name if self.hvac_action else None}")
        info_str.append(f"{self.prefix} - hvac_modes: {', '.join(mode.name for mode in self.hvac_modes)}")
        info_str.append(f"{self.prefix} - fan_modes: {', '.join(mode.name for mode in self.fan_modes)}")
        info_str.append(f"{self.prefix} - current_temperature: {self.current_temperature}")
        info_str.append(f"{self.prefix} - current_humidity: {self.current_humidity}")
        info_str.append(f"{self.prefix} - target_cool_temp: {self.target_cool_temp}")
        info_str.append(f"{self.prefix} - target_heat_temp: {self.target_heat_temp}")
        info_str.append(
            f"{self.prefix} - device_temperature_unit: {self.device_temperature_unit.name if self.device_temperature_unit else None}"
        )
        return info_str

    ZWAVE_TO_QOLSYS_HVAC_MODE: dict[ThermostatMode, QolsysHvacMode] = {
        ThermostatMode.OFF: QolsysHvacMode.OFF,
        ThermostatMode.HEAT: QolsysHvacMode.HEAT,
        ThermostatMode.FURNACE: QolsysHvacMode.HEAT,
        ThermostatMode.AUX_HEAT: QolsysHvacMode.HEAT,
        ThermostatMode.ENERGY_SAVE_HEAT: QolsysHvacMode.HEAT,
        ThermostatMode.COOL: QolsysHvacMode.COOL,
        ThermostatMode.DRY_AIR: QolsysHvacMode.DRY,
        ThermostatMode.ENERGY_SAVE_COOL: QolsysHvacMode.COOL,
        ThermostatMode.AUTO: QolsysHvacMode.AUTO,
        ThermostatMode.RESUME: QolsysHvacMode.AUTO,
        ThermostatMode.AWAY: QolsysHvacMode.AUTO,
        ThermostatMode.AUTO_CHANGEOVER: QolsysHvacMode.HEAT_COOL,
        ThermostatMode.FAN_ONLY: QolsysHvacMode.FAN_ONLY,
        ThermostatMode.MOIST_AIR: QolsysHvacMode.FAN_ONLY,
    }

    QOLSYS_TO_ZWAVE_HVAC_MODE: dict[QolsysHvacMode, ThermostatMode] = {
        QolsysHvacMode.OFF: ThermostatMode.OFF,
        QolsysHvacMode.HEAT: ThermostatMode.HEAT,
        QolsysHvacMode.COOL: ThermostatMode.COOL,
        QolsysHvacMode.AUTO: ThermostatMode.AUTO,
        QolsysHvacMode.HEAT_COOL: ThermostatMode.AUTO,
        QolsysHvacMode.FAN_ONLY: ThermostatMode.FAN_ONLY,
        QolsysHvacMode.DRY: ThermostatMode.COOL,
    }

    ZWAVE_TO_QOLSYS_FAN_MODE: dict[int, QolsysFanMode] = {
        ThermostatFanMode.AUTO_HIGH: QolsysFanMode.FAN_AUTO,
        ThermostatFanMode.AUTO_LOW: QolsysFanMode.FAN_AUTO,
        ThermostatFanMode.AUTO_MEDIUM: QolsysFanMode.FAN_AUTO,
        ThermostatFanMode.LOW: QolsysFanMode.FAN_ON,
        ThermostatFanMode.MEDIUM: QolsysFanMode.FAN_MEDIUM,
        ThermostatFanMode.HIGH: QolsysFanMode.FAN_HIGH,
        ThermostatFanMode.CIRCULATION: QolsysFanMode.FAN_CIRCULATE,
        ThermostatFanMode.HUMIDITY_CIRCULATION: QolsysFanMode.FAN_CIRCULATE,
    }

    QOLSYS_TO_ZWAVE_FAN_MODE: dict[QolsysFanMode, ThermostatFanMode] = {
        QolsysFanMode.FAN_AUTO: ThermostatFanMode.AUTO_LOW,
        QolsysFanMode.FAN_HIGH: ThermostatFanMode.HIGH,
        QolsysFanMode.FAN_MEDIUM: ThermostatFanMode.MEDIUM,
        QolsysFanMode.FAN_ON: ThermostatFanMode.LOW,
        QolsysFanMode.FAN_CIRCULATE: ThermostatFanMode.CIRCULATION,
    }

    def to_dict_event(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "service_type": self.service_name,
            "state": {
                "hvac_mode": self.hvac_mode.name if self.hvac_mode else None,
                "hvac_action": self.hvac_action.name if self.hvac_action else None,
                "current_temperature": self.current_temperature,
                "target_cool_temp": self.target_cool_temp,
                "target_heat_temp": self.target_heat_temp,
            },
            "attributes": {
                "endpoint": self.endpoint,
                "device_temperature_unit": self.device_temperature_unit.name if self.device_temperature_unit else None,
                "hvac_modes": [mode.name for mode in self.hvac_modes],
                "fan_modes": [mode.name for mode in self.fan_modes],
            },
            "capabilities": {
                "supports_target_temperature": self.supports_target_temperature(),
                "supports_target_temperature_range": self.supports_target_temperature_range(),
                "supports_humidity": self.supports_humidity(),
                "supports_fan_mode": self.supports_fan_mode(),
                "supports_turn_on": self.supports_turn_on(),
                "supports_turn_off": self.supports_turn_off(),
            },
        }

        if self.supports_humidity():
            payload["state"]["target_humidity"] = self.target_humidity

        if self.supports_fan_mode():
            payload["state"]["fan_mode"] = self.fan_mode.name if self.fan_mode else None

        return payload
