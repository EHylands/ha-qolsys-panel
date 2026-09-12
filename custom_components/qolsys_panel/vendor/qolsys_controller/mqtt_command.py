from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING, Any

from .enum_zwave import ZwaveCommandClass

if TYPE_CHECKING:
    from .controller import QolsysController

LOGGER = logging.getLogger(__name__)


class MQTTCommand:
    def __init__(
        self,
        controller: QolsysController,
        eventName: str,
    ) -> None:
        self._controller: QolsysController = controller
        self._topic: str = "mastermeid"
        self._eventName: str = eventName
        self._payload: dict[str, Any] = {}
        self._requestID = str(uuid.uuid4())
        self._qos: int = self._controller.settings.mqtt_qos
        self._responseTopic = "response_" + self._controller.settings.random_mac

        self.append("requestID", self._requestID)
        self.append("responseTopic", self._responseTopic)
        self.append("eventName", self._eventName)
        self.append("remoteMacAddress", self._controller.settings.random_mac)

    def append(self, argument: str, value: str | dict[str, Any] | int | bool | list[dict[str, Any]] | Any) -> None:
        self._payload[argument] = value

    async def send_command(self) -> dict[str, Any]:
        self._controller.enqueue_mqtt_command(self)
        return await self._controller.mqtt_command_queue.wait_for_response(
            self._requestID, timeout=self._controller.settings._mqtt_command_timeout
        )


class MQTTCommand_IpcCall(MQTTCommand):
    def __init__(
        self,
        controller: QolsysController,
        ipc_service_name: str,
        ipc_interface_name: str,
        ipc_transaction_id: int,
    ) -> None:
        super().__init__(controller, "ipcCall")
        self.append("ipcServiceName", ipc_service_name)
        self.append("ipcInterfaceName", ipc_interface_name)
        self.append("ipcTransactionID", ipc_transaction_id)

    def append_ipc_request(self, ipc_request: list[dict[str, Any]]) -> None:
        self.append("ipcRequest", ipc_request)


class MQTTCommand_Panel(MQTTCommand_IpcCall):
    def __init__(
        self,
        controller: "QolsysController",
    ) -> None:
        super().__init__(
            controller=controller,
            ipc_service_name="qinternalservice",
            ipc_interface_name="android.os.IQInternalService",
            ipc_transaction_id=7,
        )


class MQTTCommand_ZWave(MQTTCommand_IpcCall):
    def __init__(
        self,
        controller: "QolsysController",
        node_id: str,
        endpoint: str,
        zwave_command: list[int],
    ) -> None:
        super().__init__(
            controller=controller,
            ipc_service_name="qzwaveservice",
            ipc_interface_name="android.os.IQZwaveService",
            ipc_transaction_id=47,
        )

        ipc_request: list[dict[str, Any]] = [
            {
                # Node ID
                "dataType": "int",
                "dataValue": int(node_id),
            },
            {
                # End Point
                "dataType": "int",
                "dataValue": int(endpoint),
            },
            {
                # Z-Wave Payload
                "dataType": "byteArray",
                "dataValue": zwave_command,
            },
            {
                # Transmit option ?
                "dataType": "int",
                "dataValue": 0,
            },
            {
                # Priority
                "dataType": "int",
                "dataValue": 106,
            },
            {
                # Callback ?
                "dataType": "byteArray",
                "dataValue": [0],
            },
        ]

        self.append_ipc_request(ipc_request)


class MQTTCommand_ZWave_Old(MQTTCommand_IpcCall):
    def __init__(
        self,
        controller: "QolsysController",
        node_id: str,
        endpoint: int,
        secure_level: int,
        zwave_command_array: list[list[int]],
    ) -> None:
        super().__init__(
            controller=controller,
            ipc_service_name="zwaveservice",
            ipc_interface_name="zwaveservice",
            ipc_transaction_id=28,
        )

        def convert_to_multi_endpoint_command(zwave_command: list[int], endpoint: int) -> list[int]:
            modified_command = [ZwaveCommandClass.MultiChannel.value, 0x0D, 0, endpoint]
            modified_command.extend(zwave_command)
            return modified_command

        final_command: list[int] = []
        final_command.append(len(zwave_command_array))

        for command in zwave_command_array:
            if endpoint != 0:
                command = convert_to_multi_endpoint_command(command, endpoint)

            final_command.append(len(command))
            final_command.append(secure_level)
            final_command.extend(command)

        ipc_request: list[dict[str, Any]] = [
            {
                # Node ID
                "dataType": "int",
                "dataValue": int(node_id),
            },
            {
                # Priority
                "dataType": "int",
                "dataValue": 104,
            },
            {
                "dataType": "int",
                "dataValue": 0,
            },
            {
                # Command Array Length
                "dataType": "int",
                "dataValue": len(final_command),
            },
            {
                # Command Array
                "dataType": "byteArray",
                "dataValue": final_command,
            },
        ]

        self.append_ipc_request(ipc_request)


class MQTTCommand_Automation(MQTTCommand_IpcCall):
    def __init__(
        self, controller: "QolsysController", virtual_node_id: int, endpoint: int, operation_type: int, result: str
    ) -> None:
        super().__init__(
            controller=controller,
            ipc_service_name="qautomationservice",
            ipc_interface_name="android.os.IQAutomationService",
            ipc_transaction_id=1,
        )

        dict_operation: dict[str, Any] = {
            "operation_type": operation_type,
            "node_id": virtual_node_id,
            "token": 0,
            "expected_result": result,
            "source": 0,
            "endpoint": endpoint,
            "request_type": "_Operations",
        }

        ipc_request = [
            {
                "dataType": "string",
                "dataValue": json.dumps(dict_operation),
            }
        ]

        self.append_ipc_request(ipc_request)
