from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..automation.service_status import StatusService

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice


LOGGER = logging.getLogger(__name__)


class StatusServiceZwave(StatusService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)

    def supports_status(self) -> bool:
        return True

    def update_automation_service(self) -> None:
        from ..automation_zwave.device import QolsysAutomationDeviceZwave

        if isinstance(self.automation_device, QolsysAutomationDeviceZwave):
            self.is_malfunctioning = self.automation_device.node_status.lower() != "normal"
