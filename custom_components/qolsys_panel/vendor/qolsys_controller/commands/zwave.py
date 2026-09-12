from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..automation_zwave.device import QolsysAutomationDeviceZwave
from ..automation_zwave.service_cover import CoverServiceZwave
from ..automation_zwave.service_light import LightServiceZwave
from ..automation_zwave.service_lock import LockServiceZwave
from ..automation_zwave.service_siren import SirenServiceZwave
from ..automation_zwave.service_thermostat import ThermostatServiceZwave
from ..automation_zwave.service_valve import ValveServiceZwave
from ..enum_qolsys import QolsysPanelType, QolsysTemperatureUnit
from ..enum_zwave import ThermostatFanMode, ThermostatMode, ThermostatSetpointMode, ZwaveCommandClass
from ..errors import InvalidVirtualNodeError, ServiceNotFoundError
from ..mqtt_command import MQTTCommand_ZWave, MQTTCommand_ZWave_Old

if TYPE_CHECKING:
    from ..controller import QolsysController

LOGGER = logging.getLogger(__name__)


class ZWaveCommands:
    def __init__(self, controller: QolsysController) -> None:
        self._controller = controller

    async def barrier_operator_set(self, node_id: str, endpoint: str, status: int) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending barrier_operator_set command  - Node(%s) - Status(%s)", node_id, status)

        node = self._controller.state.automation_device(node_id)
        if not isinstance(node, QolsysAutomationDeviceZwave):
            raise InvalidVirtualNodeError(node_id)

        service = node.service_get(CoverServiceZwave, int(endpoint))
        if not isinstance(service, CoverServiceZwave):
            raise ServiceNotFoundError(node_id, endpoint, "CoverServiceZwave")

        barrier_operator_set = [ZwaveCommandClass.BarrierOperator.value, 1, status]
        command: MQTTCommand_ZWave | MQTTCommand_ZWave_Old
        if self._controller.panel.product_type == QolsysPanelType.IQ_PANEL_2_PLUS:
            secure_level = 1
            command = MQTTCommand_ZWave_Old(self._controller, node_id, int(endpoint), secure_level, [barrier_operator_set])
        else:
            command = MQTTCommand_ZWave(self._controller, node_id, endpoint, barrier_operator_set)

        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving barrier_operator_set command")
        return response

    async def doorlock_set(self, node_id: str, endpoint: str, locked: bool) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending zwave_doorlock_set command - Node(%s) - Locked(%s)", node_id, locked)

        node = self._controller.state.automation_device(node_id)
        if not isinstance(node, QolsysAutomationDeviceZwave):
            raise InvalidVirtualNodeError(node_id)

        service = node.service_get(LockServiceZwave, int(endpoint))
        if not isinstance(service, LockServiceZwave):
            raise ServiceNotFoundError(node_id, endpoint, "LockServiceZwave")

        # 0 unlocked, 255 locked
        lock_mode = 0
        if locked:
            lock_mode = 255

        doorlock_set = [ZwaveCommandClass.DoorLock.value, 1, lock_mode]
        command: MQTTCommand_ZWave | MQTTCommand_ZWave_Old
        if self._controller.panel.product_type == QolsysPanelType.IQ_PANEL_2_PLUS:
            secure_level = 1
            command = MQTTCommand_ZWave_Old(self._controller, node_id, int(endpoint), secure_level, [doorlock_set])
        else:
            command = MQTTCommand_ZWave(self._controller, node_id, endpoint, doorlock_set)

        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving zwave_doorlock_set command")
        return response

    async def switch_multilevel_set(self, node_id: str, endpoint: str, level: int) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending switch_multilevel_set command  - Node(%s) - Level(%s)", node_id, level)

        node = self._controller.state.automation_device(node_id)
        if not isinstance(node, QolsysAutomationDeviceZwave):
            raise InvalidVirtualNodeError(node_id)

        service = node.service_get(LightServiceZwave, int(endpoint))
        if not isinstance(service, LightServiceZwave):
            raise ServiceNotFoundError(node_id, endpoint, "LightServiceZwave")

        switch_set = [ZwaveCommandClass.SwitchMultilevel.value, 1, level]
        command: MQTTCommand_ZWave | MQTTCommand_ZWave_Old
        if self._controller.panel.product_type == QolsysPanelType.IQ_PANEL_2_PLUS:
            secure_level = 1
            command = MQTTCommand_ZWave_Old(self._controller, node_id, int(endpoint), secure_level, [switch_set])
        else:
            command = MQTTCommand_ZWave(self._controller, node_id, endpoint, switch_set)

        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving switch_multilevel_set command")
        return response

    async def switch_binary_set(self, node_id: str, endpoint: str, status: bool) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending zwave_switch_binary_set command  - Node(%s) - Status(%s)", node_id, status)
        node = self._controller.state.automation_device(node_id)

        if not isinstance(node, QolsysAutomationDeviceZwave):
            raise InvalidVirtualNodeError(node_id)

        service = node.service_get(LightServiceZwave, int(endpoint))
        if not isinstance(service, (LightServiceZwave, ValveServiceZwave, SirenServiceZwave)):
            raise ServiceNotFoundError(node_id, endpoint, "LightServiceZwave, ValveService or SirenService")

        level = 0
        if status:
            level = 255

        switch_set = [ZwaveCommandClass.SwitchBinary.value, 1, level]
        command: MQTTCommand_ZWave | MQTTCommand_ZWave_Old
        if self._controller.panel.product_type == QolsysPanelType.IQ_PANEL_2_PLUS:
            secure_level = 1
            command = MQTTCommand_ZWave_Old(self._controller, node_id, int(endpoint), secure_level, [switch_set])
        else:
            command = MQTTCommand_ZWave(self._controller, node_id, endpoint, switch_set)

        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving set_zwave_switch_binary command")
        return response

    async def thermostat_fan_mode_set(self, node_id: str, endpoint: str, fan_mode: ThermostatFanMode) -> dict[str, Any]:
        LOGGER.debug(
            "MQTT Panel Client - Sending zwave_thermostat_fan_mode_set command - Node(%s) - FanMode(%s)",
            node_id,
            fan_mode.name,
        )

        node = self._controller.state.automation_device(node_id)
        if not isinstance(node, QolsysAutomationDeviceZwave):
            raise InvalidVirtualNodeError(node_id)

        service = node.service_get(ThermostatServiceZwave, int(endpoint))
        if not isinstance(service, ThermostatServiceZwave):
            raise ServiceNotFoundError(node_id, endpoint, "ThermostatServiceZwave")

        fan_command = [ZwaveCommandClass.ThermostatFanMode.value, 1, fan_mode]
        command: MQTTCommand_ZWave | MQTTCommand_ZWave_Old
        if self._controller.panel.product_type == QolsysPanelType.IQ_PANEL_2_PLUS:
            secure_level = 1
            command = MQTTCommand_ZWave_Old(self._controller, node_id, int(endpoint), secure_level, [fan_command])
        else:
            command = MQTTCommand_ZWave(self._controller, node_id, endpoint, fan_command)

        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving zwave_thermostat_fan_mode_set command")
        return response

    async def thermostat_mode_set(self, node_id: str, endpoint: str, mode: ThermostatMode) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending zwave_thermostat_mode_set command - Node(%s) - Mode(%s)", node_id, mode.name)
        node = self._controller.state.automation_device(node_id)

        if not isinstance(node, QolsysAutomationDeviceZwave):
            raise InvalidVirtualNodeError(node_id)

        service = node.service_get(ThermostatServiceZwave, int(endpoint))
        if not isinstance(service, ThermostatServiceZwave):
            raise ServiceNotFoundError(node_id, endpoint, "ThermostatServiceZwave")

        mode_command = [ZwaveCommandClass.ThermostatMode.value, 1, int(mode)]
        command: MQTTCommand_ZWave | MQTTCommand_ZWave_Old
        if self._controller.panel.product_type == QolsysPanelType.IQ_PANEL_2_PLUS:
            secure_level = 1
            command = MQTTCommand_ZWave_Old(self._controller, node_id, int(endpoint), secure_level, [mode_command])
        else:
            command = MQTTCommand_ZWave(self._controller, node_id, endpoint, mode_command)

        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving zwave_thermostat_mode_set command")
        return response

    async def thermostat_setpoint_set(
        self, node_id: str, endpoint: str, mode: ThermostatSetpointMode, setpoint: int
    ) -> dict[str, Any]:
        node = self._controller.state.automation_device(node_id)
        if not isinstance(node, QolsysAutomationDeviceZwave):
            raise InvalidVirtualNodeError(node_id)

        service = node.service_get(ThermostatServiceZwave, int(endpoint))
        if not isinstance(service, ThermostatServiceZwave):
            raise ServiceNotFoundError(node_id, endpoint, "ThermostatServiceZwave")

        scale: int = 0
        if service.device_temperature_unit == QolsysTemperatureUnit.FAHRENHEIT:
            scale = 1

        precision: int = 1
        size: int = 2
        pss = (precision << 5) | (scale << 3) | size
        temp_int = int(round(setpoint * (10**precision)))
        temp_bytes = temp_int.to_bytes(size, byteorder="big", signed=True)

        setpointmode = ThermostatSetpointMode.HEATING
        if mode == ThermostatSetpointMode.COOLING:
            setpointmode = mode

        zwave_bytes: list[int] = [
            0x43,  # Thermostat Setpoint
            0x01,  # SET
            setpointmode.value,
            pss,
        ] + list(temp_bytes)

        LOGGER.debug(
            "MQTT Panel Client - Sending zwave_thermostat_setpoint_set - Node(%s) - Mode(%s) - Setpoint(%s): %s",
            node_id,
            mode.value,
            setpoint,
            zwave_bytes,
        )

        command: MQTTCommand_ZWave | MQTTCommand_ZWave_Old
        if self._controller.panel.product_type == QolsysPanelType.IQ_PANEL_2_PLUS:
            secure_level = 1
            command = MQTTCommand_ZWave_Old(self._controller, node_id, int(endpoint), secure_level, [zwave_bytes])
        else:
            command = MQTTCommand_ZWave(self._controller, node_id, endpoint, zwave_bytes)

        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving zwave_thermostat_setpoint_set command:%s", response)
        return response
