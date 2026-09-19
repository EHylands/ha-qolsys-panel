import logging
from typing import TYPE_CHECKING

from ..automation.service_cover import CoverService
from ..enum_adc import vdFuncLocalControl, vdFuncName, vdFuncState, vdFuncType

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice


LOGGER = logging.getLogger(__name__)


class CoverServiceADC(CoverService):
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

    async def open(self) -> None:
        self.is_opening = True
        self.is_closing = False
        self._is_opening = False

        await self.automation_device.controller.commands.adc.virtual_device_action(
            self.automation_device.virtual_node_id, self.endpoint, vdFuncState.ON
        )

    async def close(self) -> None:
        self.is_opening = False
        self.is_closing = True
        self._is_closing = False

        await self.automation_device.controller.commands.adc.virtual_device_action(
            self.automation_device.virtual_node_id, self.endpoint, vdFuncState.OFF
        )

    async def stop(self) -> None:
        pass

    async def set_current_position(self, position: int) -> None:
        pass

    def supports_open(self) -> bool:
        return True

    def supports_close(self) -> bool:
        return True

    def supports_stop(self) -> bool:
        return False

    def supports_position(self) -> bool:
        return False

    def update_adc_service(
        self,
        local_control: vdFuncLocalControl,
        func_name: vdFuncName,
        func_type: vdFuncType,
        func_state: vdFuncState,
        timestamp: str,
    ) -> None:
        self.is_closed = func_state == vdFuncState.OFF
        self._func_type = func_type

    def update_automation_service(self) -> None:
        pass
