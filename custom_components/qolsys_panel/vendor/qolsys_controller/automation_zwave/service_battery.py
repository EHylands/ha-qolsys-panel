from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..automation.service_battery import BatteryService

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice


LOGGER = logging.getLogger(__name__)


class BatteryServiceZwave(BatteryService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device, endpoint)

    def supports_battery_low(self) -> bool:
        return False

    def supports_battery_level(self) -> bool:
        try:
            level = int(self.automation_device._node_battery_level_value)
            return 0 <= level <= 100
        except (ValueError, TypeError):
            return False

    def update_automation_service(self) -> None:
        if self.supports_battery_level():
            try:
                self.battery_level = int(self.automation_device._node_battery_level_value)
            except (ValueError, TypeError):
                LOGGER.error(
                    "%s - update_automation_service - error parsing node_battery_level_value: %s",
                    self.prefix,
                    self.automation_device._node_battery_level_value,
                )
