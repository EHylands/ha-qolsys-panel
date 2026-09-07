from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from ..automation.device import QolsysAutomationDevice
from ..automation.service_meter import MeterService
from ..automation.service_sensor import SensorService
from ..automation_zwave.service_light import LightServiceZwave
from ..automation_zwave.service_lock import LockServiceZwave
from ..automation_zwave.service_meter import MeterServiceZwave
from ..automation_zwave.service_outlet import OutletServiceZwave
from ..automation_zwave.service_sensor import SensorServiceZwave
from ..automation_zwave.service_siren import SirenServiceZwave
from ..automation_zwave.service_status import StatusServiceZwave
from ..automation_zwave.service_thermostat import ThermostatServiceZwave
from ..automation_zwave.service_valve import ValveServiceZwave
from ..enum_qolsys import AutomationDeviceProtocol, QolsysMeterType, map_to_qolsys_meter_scale
from ..enum_zwave import ZwaveCommandClass, ZwaveDeviceClass
from ..mqtt_command import MQTTCommand_ZWave

if TYPE_CHECKING:
    from ..controller import QolsysController


LOGGER = logging.getLogger(__name__)


class QolsysAutomationDeviceZwave(QolsysAutomationDevice):
    def __init__(self, controller: QolsysController, zwave_dict: dict[str, str], dict: dict[str, str]) -> None:
        super().__init__(controller, dict)

        # Base Z-Wave Device Properties
        self._id: str = zwave_dict.get("_id", "")
        self._node_id: str = zwave_dict.get("node_id", "")
        self._node_name: str = zwave_dict.get("node_name", "")
        self._node_type: str = zwave_dict.get("node_type", "")
        self._node_status: str = zwave_dict.get("node_status", "")
        self._partition_id: str = zwave_dict.get("partition_id", "")
        self._node_secure_cmd_cls: str = zwave_dict.get("node_secure_cmd_cls", "")
        self._node_battery_level: str = zwave_dict.get("node_battery_level", "")
        # self._node_battery_level_value: str = zwave_dict.get("node_battery_level_value", "")
        self._is_node_listening_node: str = zwave_dict.get("is_node_listening_node", "")
        self._basic_report_value: str = zwave_dict.get("basic_report_value", "")
        self._switch_multilevel_report_value: str = zwave_dict.get("switch_multilevel_report_value", "")
        self._basic_device_type: str = zwave_dict.get("basic_device_type", "")
        self._generic_device_type: str = zwave_dict.get("generic_device_type", "")
        self._specific_device_type: str = zwave_dict.get("specific_device_type", "")
        self._num_secure_command_class: str = zwave_dict.get("num_secure_command_class", "")
        self._secure_command_class: str = zwave_dict.get("secure_command_class", "")
        self._manufacture_id: str = zwave_dict.get("manufacture_id", "")
        self._product_type: str = zwave_dict.get("product_type", "")
        self._device_protocol: str = zwave_dict.get("device_protocol", "")
        self._paired_status: str = zwave_dict.get("paired_status", "")
        self._is_device_sleeping: str = zwave_dict.get("is_device_sleeping", "")
        self._is_device_hidden: str = zwave_dict.get("is_device_hidden", "")
        self._last_updated_date: str = zwave_dict.get("last_updated_date", "")
        self._command_class_list: str = zwave_dict.get("command_class_list", "")
        self._meter_capabilities: str = ""
        self._multisensor_capabilities: str = ""

        self._notification_capabilities = zwave_dict.get("notification_capabilities", "")
        self._multi_channel_details = zwave_dict.get("multi_channel_details", "")
        self._endpoint = zwave_dict.get("endpoint", "")
        self._endpoint_details = zwave_dict.get("endpoint_details", "")

        # Fix Meter multichannel endpoint
        self._FIX_MULTICHANNEL_METER_ENDPOINT: bool = False

        # Set protocol
        self._protocol = AutomationDeviceProtocol.ZWAVE

        # Add Base Services
        self.service_add_status_service(endpoint=0)
        self.service_add_battery_service(endpoint=0)
        self.multisensor_capabilities: str = zwave_dict.get("multisensor_capabilities", "")
        self.meter_capabilities: str = zwave_dict.get("meter_capabilities", "")

        super().update_automation_services()

    def update_zwave_device(self, data: dict[str, str]) -> None:
        self.start_batch_update()

        if "multisensor_capabilities" in data:
            self.multisensor_capabilities = data.get("multisensor_capabilities", "")

        if "meter_capabilities" in data:
            self.meter_capabilities = data.get("meter_capabilities", "")

        if "node_status" in data:
            self.node_status = data.get("node_status", "")

        if "command_class_list" in data:
            self._command_class_list = data.get("command_class_list", "")

        self.end_batch_update()

    def update_raw(self, payload: bytes, endpoint: int = 0) -> None:
        try:
            command_class = payload[0]
            LOGGER.debug(
                "%s - endpoint%s - update_raw - command class: 0x%02X: %s", self.prefix, endpoint, command_class, payload.hex()
            )

            match command_class:
                case ZwaveCommandClass.SwitchBinary:
                    self.parse_command_25(payload, endpoint)

                case ZwaveCommandClass.Meter:
                    if self._FIX_MULTICHANNEL_METER_ENDPOINT:
                        self.parse_command_32(payload, endpoint)

                case ZwaveCommandClass.MultiChannel:
                    if payload[1] == 0x0D:
                        source_endpoint = payload[2]
                        self.update_raw(payload[4:], source_endpoint)

                case ZwaveCommandClass.ThermostatOperatingState:
                    LOGGER.debug("%s - Received ThermostatOperatingState report %s", self.prefix, payload.hex())

        except IndexError:
            LOGGER.debug("update_raw: invalid payload:%s", payload)

    def parse_command_25(self, payload: bytes, endpoint: int) -> None:
        command = payload[1]

        if command == 0x03:
            # Update Valve Service at specified endpoint
            valve_service = self.service_get(ValveServiceZwave, endpoint)
            if isinstance(valve_service, ValveServiceZwave):
                if payload[2] == 0xFF:
                    valve_service.is_closed = False
                elif payload[2] == 0x00:
                    valve_service.is_closed = True
                else:
                    LOGGER.warning("Unexpected Binary Switch value 0x%02X for node %s", payload[2], self.virtual_node_id)

                valve_service.is_closed = payload[2] == 0x00

            # Update Siren Service at specified endpoint
            siren_service = self.service_get(SirenServiceZwave, endpoint)
            if isinstance(siren_service, SirenServiceZwave):
                if payload[2] == 0xFF:
                    siren_service._is_on = True
                elif payload[2] == 0x00:
                    siren_service._is_on = False
                else:
                    LOGGER.warning("Unexpected Binary Switch value 0x%02X for node %s", payload[2], self.virtual_node_id)

            # Update Outlet Service at specified endpoint
            outlet_service = self.service_get(OutletServiceZwave, endpoint)
            if isinstance(outlet_service, OutletServiceZwave):
                outlet_service.is_on = payload[2] == 0xFF

    def parse_command_32(self, payload: bytes, endpoint: int) -> None:
        command = payload[1]

        # Process report
        if command == 0x02:
            props = payload[2]
            meter_type = props & 0x1F
            # rateType = (props & 0x60) >> 5
            size = payload[3] & 0x07
            scale_msb = (props & 0x80) >> 7
            scale_lsb = (payload[3] & 0x18) >> 3
            scale = (scale_msb << 2) | scale_lsb
            precision = (payload[3] & 0xE0) >> 5
            value = int.from_bytes(payload[4 : 4 + size], "big") / (10.0**precision)

            # Update Meter Service at specified endpoint
            meter_service = self.service_get(MeterServiceZwave, endpoint)
            if not isinstance(meter_service, MeterServiceZwave):
                LOGGER.error("%s - Received Meter Report for endpoint %s but no MeterService found", self.prefix, endpoint)
                return

            if meter_service.meter_type != meter_type:
                LOGGER.error(
                    "%s - Received Meter Report for meter type %s but MeterService has meter type %s",
                    self.prefix,
                    meter_type,
                    meter_service.meter_type,
                )
                return

            qolsys_scale = map_to_qolsys_meter_scale(QolsysMeterType(meter_type), scale)

            for meter in meter_service.meters:
                if meter.unit == qolsys_scale:
                    meter.value = value
                    return

    async def zwave_report(self) -> None:
        for endpoint, service_list in self.services.items():
            for service in service_list:
                if isinstance(service, LightServiceZwave):
                    light_commands = [ZwaveCommandClass.SwitchBinary, ZwaveCommandClass.SwitchMultilevel]
                    for command in light_commands:
                        if command in self.command_class_list:
                            zwave_command = MQTTCommand_ZWave(
                                self._controller, self.virtual_node_id, str(service.endpoint), [command, 0x02]
                            )
                            await zwave_command.send_command()

                if isinstance(service, LockServiceZwave):
                    lock_commands = [ZwaveCommandClass.DoorLock]
                    for command in lock_commands:
                        if command in self.command_class_list:
                            zwave_command = MQTTCommand_ZWave(
                                self._controller, self.virtual_node_id, str(service.endpoint), [command, 0x02]
                            )
                            await zwave_command.send_command()

                if isinstance(service, ThermostatServiceZwave):
                    thermostat_commands = [
                        ZwaveCommandClass.ThermostatFanMode,
                        ZwaveCommandClass.ThermostatMode,
                        ZwaveCommandClass.ThermostatSetPoint,
                        ZwaveCommandClass.ThermostatOperatingState,
                    ]
                    for command in thermostat_commands:
                        if command in self.command_class_list:
                            zwave_command = MQTTCommand_ZWave(
                                self._controller, self.virtual_node_id, str(service.endpoint), [command, 0x02]
                            )
                            await zwave_command.send_command()

                if isinstance(service, ValveServiceZwave):
                    valve_commands = [ZwaveCommandClass.SwitchBinary]
                    for command in valve_commands:
                        if command in self.command_class_list:
                            zwave_command = MQTTCommand_ZWave(
                                self._controller, self.virtual_node_id, str(service.endpoint), [command, 0x02]
                            )
                            await zwave_command.send_command()

                if isinstance(service, SirenServiceZwave):
                    siren_commands = [ZwaveCommandClass.SwitchBinary]
                    for command in siren_commands:
                        if command in self.command_class_list:
                            zwave_command = MQTTCommand_ZWave(
                                self._controller, self.virtual_node_id, str(service.endpoint), [command, 0x02]
                            )
                            await zwave_command.send_command()

                if isinstance(service, OutletServiceZwave):
                    if ZwaveCommandClass.SwitchBinary in self.command_class_list:
                        zwave_command = MQTTCommand_ZWave(
                            self._controller,
                            self.virtual_node_id,
                            str(service.endpoint),
                            [ZwaveCommandClass.SwitchBinary, 0x02],
                        )
                        await zwave_command.send_command()

    def to_dict_zwave(self) -> dict[str, str]:
        return {
            "_id": self._id,
            "node_id": self._node_id,
            "node_name": self._node_name,
            "node_type": self._node_type,
            "node_status": self._node_status,
            "partition_id": self._partition_id,
            "node_secure_cmd_cls": self._node_secure_cmd_cls,
            "node_battery_level": self._node_battery_level,
            "node_battery_level_value": self._node_battery_level_value,
            "is_node_listening_node": self._is_node_listening_node,
            "basic_report_value": self._basic_report_value,
            "switch_multilevel_report_value": self._switch_multilevel_report_value,
            "basic_device_type": self._basic_device_type,
            "generic_device_type": self._generic_device_type,
            "specific_device_type": self._specific_device_type,
            "num_secure_command_class": self._num_secure_command_class,
            "secure_command_class": self._secure_command_class,
            "manufacture_id": self._manufacture_id,
            "product_type": self._product_type,
            "device_protocol": self._device_protocol,
            "paired_status": self._paired_status,
            "is_device_sleeping": self._is_device_sleeping,
            "is_device_hidden": self._is_device_hidden,
            "last_updated_date": self._last_updated_date,
            "command_class_list": self._command_class_list,
            "multisensor_capabilities": self._multisensor_capabilities,
            "notification_capabilities": self._notification_capabilities,
            "multi_channel_details": self._multi_channel_details,
            "endpoint": self._endpoint,
            "endpoint_details": self._endpoint_details,
            "meter_capabilities": self._meter_capabilities,
        }

    # -----------------------------
    # properties + setters
    # -----------------------------

    @property
    def generic_device_type(self) -> ZwaveDeviceClass:
        try:
            dict = json.loads(self.extras)
            generic_type = int(dict.get("GENERIC_TYPE", "0"))
            return ZwaveDeviceClass(generic_type)
        except (ValueError, TypeError, json.JSONDecodeError):
            return ZwaveDeviceClass.Unknown

    @property
    def command_class_list(self) -> list[ZwaveCommandClass]:
        commands = []
        array = self._command_class_list.strip("[]").split(",")
        for command in array:
            try:
                commands.append(ZwaveCommandClass(int(command)))
            except (ValueError, TypeError):
                continue
        return commands

    @property
    def secure_command_class_list(self) -> list[ZwaveCommandClass]:
        commands = []
        array = self._node_secure_cmd_cls.strip("[]").split(",")
        for command in array:
            try:
                commands.append(ZwaveCommandClass(int(command)))
            except (ValueError, TypeError):
                continue
        return commands

    @property
    def multisensor_capabilities(self) -> str:
        return self._multisensor_capabilities

    @multisensor_capabilities.setter
    def multisensor_capabilities(self, value: str) -> None:
        if self._multisensor_capabilities != value:
            self._multisensor_capabilities = value

            # Update Sensor Service
            try:
                sensors_dict = json.loads(value)
                for endpoint, values in sensors_dict.items():
                    service = self.service_get(SensorService, int(endpoint))
                    if not service:
                        service = SensorServiceZwave(self, int(endpoint))
                        self.service_add(service)

                    if isinstance(service, SensorServiceZwave):
                        service.update_zwave_service(values)

            except json.JSONDecodeError:
                LOGGER.error("%s - Error parsing multilevelsensor_capabilities:%s", self.prefix)
                return

    @property
    def meter_capabilities(self) -> str:
        return self._meter_capabilities

    @meter_capabilities.setter
    def meter_capabilities(self, value: str) -> None:
        # Do not update meters if FIX_MULTICHANNEL_METER_ENDPOINT is enabled
        if self._FIX_MULTICHANNEL_METER_ENDPOINT:
            return

        if self._meter_capabilities != value:
            self._meter_capabilities = value

            # Update Meter Service
            try:
                meters_dict = json.loads(value)
                if len(meters_dict.keys()) > 1 and not self._FIX_MULTICHANNEL_METER_ENDPOINT:
                    self._FIX_MULTICHANNEL_METER_ENDPOINT = True
                    LOGGER.debug(
                        "%s - Multiple meter endpoints detected, enabling FIX_MULTICHANNEL_METER_ENDPOINT", self.prefix
                    )

                for endpoint, values in meters_dict.items():
                    service = self.service_get(MeterService, int(endpoint))
                    if not service:
                        service = MeterServiceZwave(self, int(endpoint))
                        self.service_add(service)

                    if isinstance(service, MeterServiceZwave):
                        service.update_zwave_service(values, not self._FIX_MULTICHANNEL_METER_ENDPOINT)

            except json.JSONDecodeError:
                LOGGER.error("%s - Error parsing meter_capabilities:%s", self.prefix)
                return

    @property
    def node_status(self) -> str:
        return self._node_status

    @node_status.setter
    def node_status(self, value: str) -> None:
        if self._node_status != value:
            self._node_status = value
            for service in self.service_get_protocol(StatusServiceZwave):
                if isinstance(service, StatusServiceZwave):
                    service.update_automation_service()
