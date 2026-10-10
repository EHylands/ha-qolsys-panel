import json
import logging
from typing import TYPE_CHECKING

from ..automation.device import QolsysAutomationDevice
from ..automation.service import AutomationService
from ..enum_adc import vdFuncLocalControl, vdFuncName, vdFuncState, vdFuncType
from ..enum_qolsys import AutomationDeviceProtocol, QolsysNotification
from ..observable import Event

if TYPE_CHECKING:
    from ..controller import QolsysController

LOGGER = logging.getLogger(__name__)


class QolsysAutomationDeviceADC(QolsysAutomationDevice):
    def __init__(self, controller: "QolsysController", adc_dict: dict[str, str]) -> None:
        super().__init__(controller, {})

        self._id: str = adc_dict.get("_id", "")
        self._partition_id: str = adc_dict.get("partition_id", "")
        self._device_id: str = adc_dict.get("device_id", "")
        self._name: str = adc_dict.get("name", "")
        self._type: str = adc_dict.get("type", "")
        self._create_time: str = adc_dict.get("create_time", "")
        self._created_by: str = adc_dict.get("created_by", "")
        self._update_time: str = adc_dict.get("update_time", "")
        self._updated_by: str = adc_dict.get("updated_by", "")
        self._device_zone_list: str = adc_dict.get("device_zone_list", "")
        self._func_list = ""

        # Set virtual_node_id to device_id for now, since ADC devices don't have a nodeid like zwave/powerg devices
        self.start_batch_update()
        self._protocol = AutomationDeviceProtocol.ADC
        self._device_type = "VirtualADC"
        self._virtual_node_id = self._device_id
        self._device_name = self._name
        self._node_battery_level_value = "-1"
        self.func_list = adc_dict.get("func_list", "")
        self.end_batch_update()

    def update_adc_device(self, adc_data: dict[str, str]) -> None:
        # Check if we are updating same virtual_node_id
        virtual_node_id_update = adc_data.get("device_id", "")
        if virtual_node_id_update != self._virtual_node_id:
            LOGGER.error(
                "Updating AutDev%s (%s) with %s (different virtual_node_id)",
                self._virtual_node_id,
                self._device_name,
                virtual_node_id_update,
            )
            return

        self.start_batch_update()

        if "partition_id" in adc_data:
            self.partition_id = adc_data.get("partition_id", "")

        if "name" in adc_data:
            self.device_name = adc_data.get("name", "")

        if "type" in adc_data:
            self._type = adc_data.get("type", "")

        if "func_list" in adc_data:
            self.func_list = adc_data.get("func_list", "")

        self.end_batch_update()

    def to_dict_adc(self) -> dict[str, str]:
        return {
            "_id": self._id,
            "partition_id": self._partition_id,
            "device_id": self._virtual_node_id,
            "name": self._device_name,
            "type": self._type,
            "create_time": self._create_time,
            "created_by": self._created_by,
            "update_time": self._update_time,
            "updated_by": self._updated_by,
            "device_zone_list": self._device_zone_list,
            "func_list": self._func_list,
        }

    def service_get_adc(self, endpoint: int) -> AutomationService | None:
        # In AutomationDeviceADC, only 1 service per endpoint is expected
        service_list = self._services.get(endpoint, None)
        if service_list is not None and len(service_list) > 0:
            return service_list[0]
        return None

    def service_add_adc(
        self,
        id: int,
        local_control: vdFuncLocalControl,
        func_name: vdFuncName,
        func_type: vdFuncType,
        func_state: vdFuncState,
        timestamp: str,
    ) -> None:
        # Garage Door Service
        if func_name == vdFuncName.OPEN_CLOSE and func_type == vdFuncType.BINARY_ACTUATOR:
            self.service_add_cover_service(endpoint=id)
            self.notify(Event(QolsysNotification.AUTOMATION_UPDATE, self, self.to_dict_event()))

        # Light Service
        if func_name == vdFuncName.OFF_ON and func_type == vdFuncType.LIGHT:
            self.service_add_light_service(endpoint=id)
            self.notify(Event(QolsysNotification.AUTOMATION_UPDATE, self, self.to_dict_event()))

        # Malfunction Service
        if func_name == vdFuncName.MALFUNCTION and func_type == vdFuncType.MALFUNCTION:
            self.service_add_status_service(endpoint=id)
            self.notify(Event(QolsysNotification.AUTOMATION_UPDATE, self, self.to_dict_event()))

    # -----------------------------
    # properties + setters
    # -----------------------------

    @property
    def func_list(self) -> str:
        return self._func_list

    @func_list.setter
    def func_list(self, value: str) -> None:
        if self._func_list != value:
            LOGGER.debug("%s - func_list: %s", self.prefix, value)
            self._func_list = value

            try:
                json_func_list = json.loads(self._func_list)
                new_service_id: list[int] = []
                self.start_batch_update()

                for function in json_func_list:
                    try:
                        id = function.get("vdFuncId")
                        local_control = vdFuncLocalControl(function.get("vdFuncLocalControl"))
                        func_name = vdFuncName(function.get("vdFuncName"))
                        func_type = vdFuncType(function.get("vdFuncType"))
                        func_state = vdFuncState(function.get("vdFuncState"))
                        timestamp = function.get("vdFuncBackendTimestamp")
                        new_service_id.append(id)

                        service = self.service_get_adc(endpoint=id)
                        if service is None:
                            self.service_add_adc(id, local_control, func_name, func_type, func_state, timestamp)
                            service = self.service_get_adc(endpoint=id)

                        if service is not None:
                            service.update_adc_service(  # type: ignore[attr-defined]
                                local_control=local_control,
                                func_name=func_name,
                                func_type=func_type,
                                func_state=func_state,
                                timestamp=timestamp,
                            )

                    except ValueError as e:
                        LOGGER.error("Error converting value:", e)
                        continue

                self.end_batch_update()

            except json.JSONDecodeError as e:
                LOGGER.error("ADC%s - Error parsing JSON:", self.device_id, e)
