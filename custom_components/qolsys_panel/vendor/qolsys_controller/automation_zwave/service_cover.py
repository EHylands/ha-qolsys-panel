from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..automation.service_cover import CoverService
from ..enum_zwave import ZwaveCommandClass

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice


LOGGER = logging.getLogger(__name__)


class CoverServiceZwave(CoverService):
    def __init__(
        self,
        automation_device: QolsysAutomationDevice,
        endpoint: int,
    ) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)

    async def open(self) -> None:
        self.is_opening = True
        self.is_closing = False
        self._is_opening = False

        await self.automation_device.controller.commands.zwave.barrier_operator_set(
            self.automation_device.virtual_node_id, str(self.endpoint), 0xFF
        )

    async def close(self) -> None:
        self.is_opening = False
        self.is_closing = True
        self._is_closing = False

        await self.automation_device.controller.commands.zwave.barrier_operator_set(
            self.automation_device.virtual_node_id, str(self.endpoint), 0x00
        )

    async def stop(self) -> None:
        pass

    async def set_current_position(self, position: int) -> None:
        pass

    def supports_open(self) -> bool:
        from ..automation_zwave.device import QolsysAutomationDeviceZwave

        if isinstance(self.automation_device, QolsysAutomationDeviceZwave):
            return ZwaveCommandClass.BarrierOperator in self.automation_device.command_class_list

        LOGGER.error("%s - supports_open - Error, not a QolsysAutomationDeviceZwave", self.prefix)
        return False

    def supports_close(self) -> bool:
        from ..automation_zwave.device import QolsysAutomationDeviceZwave

        if isinstance(self.automation_device, QolsysAutomationDeviceZwave):
            return ZwaveCommandClass.BarrierOperator in self.automation_device.command_class_list

        LOGGER.error("%s - supports_close - Error, not a QolsysAutomationDeviceZwave", self.prefix)
        return False

    def supports_stop(self) -> bool:
        return False

    def supports_position(self) -> bool:
        return False

    def update_automation_service(self) -> None:
        super().update_automation_service()
