from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..automation.service_thermostat import ThermostatService
from ..enum_qolsys import QolsysFanMode, QolsysHvacMode
from ..enum_zwave import ThermostatMode, ThermostatSetpointMode

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice

LOGGER = logging.getLogger(__name__)


class ThermostatServiceZwave(ThermostatService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)

    async def turn_on(self) -> None:
        pass

    async def turn_off(self) -> None:
        await self.automation_device.controller.commands.zwave.thermostat_mode_set(
            self.automation_device.virtual_node_id, str(self.endpoint), ThermostatMode.OFF
        )

    async def set_temperature(self, temperature: float, mode: QolsysHvacMode) -> None:
        if mode not in (QolsysHvacMode.HEAT, QolsysHvacMode.COOL):
            LOGGER.error(
                "%s[%s] ThermostatServiceZwave - set_temperature - unsupported hvac_mode: %s",
                self.automation_device.prefix,
                self.endpoint,
                mode,
            )
            return

        if mode not in self.hvac_modes:
            LOGGER.error(
                "%s[%s] ThermostatServiceZwave - set_temperature - hvac_mode not supported by device: %s",
                self.automation_device.prefix,
                self.endpoint,
                mode,
            )
            return

        setpoint_mode: ThermostatSetpointMode = ThermostatSetpointMode.HEATING
        if mode == QolsysHvacMode.COOL:
            setpoint_mode = ThermostatSetpointMode.COOLING

        await self.automation_device.controller.commands.zwave.thermostat_setpoint_set(
            self.automation_device.virtual_node_id, str(self.endpoint), setpoint_mode, int(temperature)
        )

    async def set_hvac_mode(self, hvac_mode: QolsysHvacMode) -> None:
        zwave_thermostat_mode = self.QOLSYS_TO_ZWAVE_HVAC_MODE.get(hvac_mode, None)
        if zwave_thermostat_mode is None:
            LOGGER.error(
                "%s[%s] ThermostatServiceZwave - set_hvac_mode - unsupported hvac_mode: %s",
                self.automation_device.prefix,
                self.endpoint,
                hvac_mode,
            )
            return

        await self.automation_device.controller.commands.zwave.thermostat_mode_set(
            self.automation_device.virtual_node_id, str(self.endpoint), zwave_thermostat_mode
        )

    async def set_fan_mode(self, fan_mode: QolsysFanMode) -> None:
        zwave_fan_mode = self.QOLSYS_TO_ZWAVE_FAN_MODE.get(fan_mode, None)
        if zwave_fan_mode is None:
            LOGGER.error(
                "%s[%s] ThermostatServiceZwave - set_fan_mode - unsupported fan_mode: %s",
                self.automation_device.prefix,
                self.endpoint,
                fan_mode,
            )
            return
        await self.automation_device.controller.commands.zwave.thermostat_fan_mode_set(
            self.automation_device.virtual_node_id, str(self.endpoint), zwave_fan_mode
        )

    async def set_humidity(self, humidity: float) -> None:
        pass

    def update_automation_service(self) -> None:
        super().update_automation_service()
