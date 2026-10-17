import logging
from typing import TYPE_CHECKING

from ..automation.service_status import StatusService
from ..enum_adc import vdFuncLocalControl, vdFuncName, vdFuncState, vdFuncType

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice


LOGGER = logging.getLogger(__name__)


class StatusServiceADC(StatusService):
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

    def supports_status(self) -> bool:
        return True

    def update_adc_service(
        self,
        local_control: vdFuncLocalControl,
        func_name: vdFuncName,
        func_type: vdFuncType,
        func_state: vdFuncState,
        timestamp: str,
    ) -> None:
        self.is_malfunctioning = func_state == vdFuncState.ON
        self._func_type = func_type

    def update_automation_service(self) -> None:
        pass
