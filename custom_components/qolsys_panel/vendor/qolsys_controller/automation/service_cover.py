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


class CoverService(AutomationService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)
        self._service_name = "CoverService"
        self._current_position: int | None = None
        self._is_closed: bool = False
        self._is_opening: bool = False
        self._is_closing: bool = False

    @abstractmethod
    async def open(self) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    @abstractmethod
    async def set_current_position(self, position: int) -> None:
        pass

    @abstractmethod
    def supports_open(self) -> bool:
        pass

    @abstractmethod
    def supports_close(self) -> bool:
        pass

    @abstractmethod
    def supports_stop(self) -> bool:
        pass

    @abstractmethod
    def supports_position(self) -> bool:
        pass

    @property
    def is_closing(self) -> bool:
        return self._is_closing

    @is_closing.setter
    def is_closing(self, value: bool) -> None:
        if self._is_closing != value:
            self._is_closing = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - is_closing: %s", self.prefix, value)

    @property
    def is_opening(self) -> bool:
        return self._is_opening

    @is_opening.setter
    def is_opening(self, value: bool) -> None:
        if self._is_opening != value:
            self._is_opening = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - is_opening: %s", self.prefix, value)

    @property
    def current_position(self) -> int | None:
        return self._current_position

    @current_position.setter
    def current_position(self, value: int) -> None:
        if not (0 <= value <= 99):
            LOGGER.error("%s - level: invalid value: %s", self.prefix, value)
            self._current_position = None
            return

        if self._current_position != value:
            self._current_position = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - current_position: %s", self.prefix, value)

    @property
    def is_closed(self) -> bool:
        return self._is_closed

    @is_closed.setter
    def is_closed(self, value: bool) -> None:
        if self._is_closed != value:
            self._is_closed = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - is_closed: %s", self.prefix, value)

    def update_automation_service(self) -> None:
        self.is_closed = self.automation_device.status.lower() == "closed"

    def info(self) -> list[str]:
        info_str = []
        info_str.append(f"{self.prefix} - is_closed: {self.is_closed}")
        info_str.append(f"{self.prefix} - current_position: {self.current_position}")
        info_str.append(f"{self.prefix} - supports_open: {self.supports_open()}")
        info_str.append(f"{self.prefix} - supports_close: {self.supports_close()}")
        info_str.append(f"{self.prefix} - supports_stop: {self.supports_stop()}")
        info_str.append(f"{self.prefix} - supports_position: {self.supports_position()}")
        return info_str

    def to_dict_event(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "service_type": self.service_name,
            "state": {},
            "attributes": {
                "endpoint": self.endpoint,
            },
            "capabilities": {
                "supports_open": self.supports_open(),
                "supports_close": self.supports_close(),
                "supports_stop": self.supports_stop(),
                "supports_position": self.supports_position(),
            },
        }

        if self.supports_position():
            payload["state"]["current_position"] = self.current_position

        if self.supports_open():
            payload["state"]["is_opening"] = self.is_opening
            payload["state"]["is_closed"] = self.is_closed
            payload["state"]["is_closing"] = self.is_closing

        return payload
