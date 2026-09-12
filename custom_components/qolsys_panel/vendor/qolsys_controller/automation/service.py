from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice


class AutomationService(ABC):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        self._automation_device = automation_device
        self._endpoint: int = endpoint
        self._service_name: str = "AutomationService"

    @property
    def automation_device(self) -> "QolsysAutomationDevice":
        return self._automation_device

    @automation_device.setter
    def automation_device(self, value: "QolsysAutomationDevice") -> None:
        self._automation_device = value

    @property
    def prefix(self) -> str:
        return f"[AutDev][{self.automation_device.protocol.name}][{self.automation_device.virtual_node_id}][{self.endpoint}]({self.automation_device.device_name}) - {self.service_name}"

    @property
    def endpoint(self) -> int:
        return self._endpoint

    @endpoint.setter
    def endpoint(self, value: int) -> None:
        self._endpoint = value

    @property
    def service_name(self) -> str:
        return self._service_name

    @abstractmethod
    def info(self) -> list[str]:
        pass

    @abstractmethod
    def update_automation_service(self) -> None:
        pass

    def to_dict_event(self) -> dict[str, Any]:
        raise NotImplementedError("to_dict_event must be implemented by subclasses")
