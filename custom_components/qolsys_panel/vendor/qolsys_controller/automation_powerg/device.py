from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..automation.device import QolsysAutomationDevice
from ..enum_qolsys import QolsysNotification
from ..observable import Event

if TYPE_CHECKING:
    from ..controller import QolsysController

LOGGER = logging.getLogger(__name__)


class QolsysAutomationDevicePowerG(QolsysAutomationDevice):
    def __init__(self, controller: QolsysController, dict: dict[str, str]) -> None:
        super().__init__(controller, dict)

        self._short_device_id: str = ""

        # Add Base Services
        self.service_add_status_service(endpoint=0)
        self.service_add_battery_service(endpoint=0)

        super().update_automation_services()

    def update_power_device(self, data: dict[str, str]) -> None:
        pass

    # -----------------------------
    # properties + setters
    # -----------------------------

    @property
    def short_device_id(self) -> str:
        return self._short_device_id

    @short_device_id.setter
    def short_device_id(self, value: str) -> None:
        if value != self._short_device_id:
            self._short_device_id = value
            self.notify(Event(QolsysNotification.AUTOMATION_UPDATE, self, self.to_dict_event()))
