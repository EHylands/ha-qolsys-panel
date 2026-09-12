from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..automation.service_battery import BatteryService

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice


LOGGER = logging.getLogger(__name__)


class BatteryServiceZigbee(BatteryService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device, endpoint)

    def supports_battery_low(self) -> bool:
        return False

    def supports_battery_level(self) -> bool:
        return False

    def update_automation_service(self) -> None:
        pass
