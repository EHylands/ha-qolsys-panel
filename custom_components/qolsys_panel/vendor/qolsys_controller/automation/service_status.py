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


class StatusService(AutomationService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)
        self._service_name = "StatusService"
        self._is_malfunctioning: bool = False

    @abstractmethod
    def supports_status(self) -> bool:
        pass

    @property
    def is_malfunctioning(self) -> bool:
        return self._is_malfunctioning

    @is_malfunctioning.setter
    def is_malfunctioning(self, value: bool) -> None:
        if self._is_malfunctioning != value:
            self._is_malfunctioning = value
            Event(QolsysNotification.AUTOMATION_UPDATE, self, self.to_dict_event())
            self.automation_device.notify(Event(QolsysNotification.AUTOMATION_UPDATE, self, self.to_dict_event()))
            LOGGER.debug("%s - is_malfunctioning: %s", self.prefix, value)

    def update_automation_service(self) -> None:
        self.is_malfunctioning = self.automation_device.state.lower() != "normal"

    def info(self) -> list[str]:
        return [f"{self.prefix} - is_malfunctioning: {self.is_malfunctioning}"]

    def to_dict_event(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "service_type": self.service_name,
            "state": {},
            "attributes": {
                "endpoint": self.endpoint,
            },
            "capabilities": {
                "supports_status": self.supports_status(),
            },
        }

        if self.supports_status():
            payload["state"]["is_malfunctioning"] = self.is_malfunctioning

        return payload
