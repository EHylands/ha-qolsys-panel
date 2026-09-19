import logging
from typing import TYPE_CHECKING

from ..automation.service_light import LightService
from ..enum_adc import vdFuncLocalControl, vdFuncName, vdFuncState, vdFuncType

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice


LOGGER = logging.getLogger(__name__)


class LightServiceADC(LightService):
    def __init__(
        self,
        automation_device: "QolsysAutomationDevice",
        endpoint: int,
    ) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)
        self._func_type: vdFuncType = vdFuncType.UNKNOWN

    @property
    def func_type(self) -> vdFuncType:
        return self._func_type

    async def turn_on(self) -> None:
        await self.automation_device.controller.commands.adc.virtual_device_action(
            self.automation_device.virtual_node_id, self.endpoint, vdFuncState.ON
        )

    async def turn_off(self) -> None:
        await self.automation_device.controller.commands.adc.virtual_device_action(
            self.automation_device.virtual_node_id, self.endpoint, vdFuncState.OFF
        )

    async def set_level(self, level: int) -> None:
        pass

    def supports_level(self) -> bool:
        return False

    def update_adc_service(
        self,
        local_control: vdFuncLocalControl,
        func_name: vdFuncName,
        func_type: vdFuncType,
        func_state: vdFuncState,
        timestamp: str,
    ) -> None:
        self.is_on = func_state == vdFuncState.ON
        self._func_type = func_type

    def update_automation_service(self) -> None:
        pass
