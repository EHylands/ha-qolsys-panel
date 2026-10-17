from __future__ import annotations

import logging
from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from ..automation.service import AutomationService
from ..enum_qolsys import QolsysNotification
from ..observable import Event

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice

LOGGER = logging.getLogger(__name__)


class OutletService(AutomationService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)
        self._service_name = "OutletService"
        self._is_on: bool = False

    @abstractmethod
    async def turn_on(self) -> None:
        pass

    @abstractmethod
    async def turn_off(self) -> None:
        pass

    @property
    def is_on(self) -> bool:
        return self._is_on

    @is_on.setter
    def is_on(self, value: bool) -> None:
        if self._is_on != value:
            self._is_on = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - is_on: %s", self.prefix, value)

    def update_automation_service(self) -> None:
        self.is_on = self.automation_device.status.lower() != "off"

    def info(self) -> list[str]:
        return [f"{self.prefix} - is_on: {self.is_on}"]

    def to_dict_event(self) -> dict[str, Any]:
        return {
            "service_type": self.service_name,
            "state": {"is_on": self.is_on},
            "attributes": {"endpoint": self.endpoint},
            "capabilities": {},
        }
