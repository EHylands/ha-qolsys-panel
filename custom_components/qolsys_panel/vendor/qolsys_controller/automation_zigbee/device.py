from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..automation.device import QolsysAutomationDevice

if TYPE_CHECKING:
    from ..controller import QolsysController

LOGGER = logging.getLogger(__name__)


class QolsysAutomationDeviceZigbee(QolsysAutomationDevice):
    def __init__(self, controller: QolsysController, dict: dict[str, str]) -> None:
        super().__init__(controller, dict)

        self._short_device_id: str = ""

        # Add Base Services
        self.service_add_status_service(endpoint=0)
        self.service_add_battery_service(endpoint=0)

        super().update_automation_services()

    # -----------------------------
    # properties + setters
    # -----------------------------
