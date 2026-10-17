from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from ..automation_adc.device import QolsysAutomationDeviceADC
from ..automation_adc.service_cover import CoverServiceADC
from ..automation_adc.service_light import LightServiceADC
from ..automation_adc.service_status import StatusServiceADC
from ..enum_adc import vdFuncState
from ..errors import InvalidVirtualNodeError, ServiceNotFoundError
from ..mqtt_command import MQTTCommand_Panel

if TYPE_CHECKING:
    from ..controller import QolsysController

LOGGER = logging.getLogger(__name__)


class AdcCommands:
    def __init__(self, controller: QolsysController) -> None:
        self._controller = controller

    async def virtual_device_action(self, device_id: str, service_id: int, state: vdFuncState) -> dict[str, Any] | None:
        LOGGER.debug(
            "MQTT Panel Client: Sending virtual_device_action device: %s, service: %s state: %s",
            device_id,
            service_id,
            state.name,
        )

        device = self._controller.state.automation_device(device_id)
        if not isinstance(device, QolsysAutomationDeviceADC):
            raise InvalidVirtualNodeError(device_id)

        service = device.service_get_adc(service_id)
        if not isinstance(service, (LightServiceADC, CoverServiceADC, StatusServiceADC)):
            raise ServiceNotFoundError(device_id, str(service_id), "LightServiceADC, CoverServiceADC or StatusServiceADC")

        device_list = {
            "virtualDeviceList": [
                {
                    "virtualDeviceId": int(device_id),
                    "virtualDeviceFunctionList": [
                        {
                            "vdFuncId": service_id,
                            "vdFuncState": state,
                            "vdFuncBackendTimestamp": int(time.time() * 1000),
                            "vdFuncType": service.func_type,
                        }
                    ],
                }
            ]
        }

        virtual_command = {
            "operation_name": "send_virtual_device_description",
            "virtual_device_operation": 4,
            "virtual_device_description": json.dumps(device_list),
        }

        ipc_request = [
            {
                "dataType": "string",
                "dataValue": json.dumps(virtual_command),
            }
        ]

        LOGGER.debug("virtual command: %s", virtual_command)
        command = MQTTCommand_Panel(self._controller)
        command.append_ipc_request(ipc_request)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client: Receiving virtual_device command: %s", response)
        return response
