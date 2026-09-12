from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..automation.service_light import LightService

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice


LOGGER = logging.getLogger(__name__)


class LightServicePowerG(LightService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)

    async def turn_on(self) -> None:
        await self._automation_device.controller.commands.automation.light_on(
            int(self.automation_device.virtual_node_id), self.endpoint
        )

    async def turn_off(self) -> None:
        await self.automation_device.controller.commands.automation.light_off(
            int(self.automation_device.virtual_node_id), self.endpoint
        )

    async def set_level(self, level: int) -> None:
        pass

    def supports_level(self) -> bool:
        return False

    def update_automation_service(self) -> None:
        self.is_on = self.automation_device.status.lower() == "on"
