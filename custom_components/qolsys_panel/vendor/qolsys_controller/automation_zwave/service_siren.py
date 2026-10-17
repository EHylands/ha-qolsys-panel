from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..automation.service_siren import SirenService
from ..enum_zwave import ZwaveCommandClass

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice

LOGGER = logging.getLogger(__name__)


class SirenServiceZwave(SirenService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)
        self._service_name = "SirenService"
        self._is_on: bool = False

    async def turn_on(self) -> None:
        if self.is_on:
            LOGGER.debug("%s - turn_on: already on", self.prefix)
            return

        if ZwaveCommandClass.SwitchBinary not in self.automation_device.command_class_list:  # type: ignore[attr-defined]
            LOGGER.error("%s - siren does not support SwitchBinary command class", self.prefix)
            return

        await self.automation_device.controller.commands.zwave.switch_binary_set(
            self.automation_device.virtual_node_id, str(self.endpoint), True
        )

    async def turn_off(self) -> None:
        if not self.is_on:
            LOGGER.debug("%s - turn_off: already off", self.prefix)
            return

        if ZwaveCommandClass.SwitchBinary not in self.automation_device.command_class_list:  # type: ignore[attr-defined]
            LOGGER.error("%s - siren does not support SwitchBinary command class", self.prefix)
            return

        await self.automation_device.controller.commands.zwave.switch_binary_set(
            self.automation_device.virtual_node_id, str(self.endpoint), False
        )

    def update_automation_service(self) -> None:
        super().update_automation_service()
