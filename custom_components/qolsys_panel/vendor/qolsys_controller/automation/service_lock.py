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


class LockService(AutomationService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)
        self._service_name = "LockService"
        self._is_locked: bool = False
        self._is_locking: bool = False
        self._is_unlocking: bool = False
        self._is_open: bool = False
        self._is_opening: bool = False
        self._is_closing: bool = False
        self._is_jammed: bool = False

    @abstractmethod
    async def lock(self) -> None:
        pass

    @abstractmethod
    async def unlock(self) -> None:
        pass

    @abstractmethod
    async def open(self) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    @abstractmethod
    def supports_lock(self) -> bool:
        pass

    @abstractmethod
    def supports_open(self) -> bool:
        pass

    @abstractmethod
    def supports_jam(self) -> bool:
        pass

    @property
    def is_locked(self) -> bool:
        return self._is_locked

    @is_locked.setter
    def is_locked(self, value: bool) -> None:
        if self._is_locked != value:
            self._is_locked = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - is_locked: %s", self.prefix, value)

    @property
    def is_locking(self) -> bool:
        return self._is_locking

    @is_locking.setter
    def is_locking(self, value: bool) -> None:
        if self._is_locking != value:
            self._is_locking = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - is_locking: %s", self.prefix, value)

    @property
    def is_unlocking(self) -> bool:
        return self._is_unlocking

    @is_unlocking.setter
    def is_unlocking(self, value: bool) -> None:
        if self._is_unlocking != value:
            self._is_unlocking = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - is_unlocking: %s", self.prefix, value)

    @property
    def is_open(self) -> bool:
        return self._is_open

    @is_open.setter
    def is_open(self, value: bool) -> None:
        if self._is_open != value:
            self._is_open = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - is_open: %s", self.prefix, value)

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
    def is_jammed(self) -> bool:
        return self._is_jammed

    @is_jammed.setter
    def is_jammed(self, value: bool) -> None:
        if self._is_jammed != value:
            self._is_jammed = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - is_jammed: %s", self.prefix, value)

    def info(self) -> list[str]:
        info_str = []
        info_str.append(f"{self.prefix} - supports_lock: {self.supports_lock()}")
        info_str.append(f"{self.prefix} - supports_open: {self.supports_open()}")
        info_str.append(f"{self.prefix} - supports_jam: {self.supports_jam()}")

        if self.supports_lock():
            info_str.append(f"{self.prefix} - is_locked: {self.is_locked}")
        if self.supports_open():
            info_str.append(f"{self.prefix} - is_open: {self.is_open}")
        if self.supports_jam():
            info_str.append(f"{self.prefix} - is_jammed: {self.is_jammed}")

        return info_str

    def to_dict_event(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "service_type": self.service_name,
            "state": {},
            "attributes": {
                "endpoint": self.endpoint,
            },
            "capabilities": {
                "supports_lock": self.supports_lock(),
                "supports_open": self.supports_open(),
                "supports_jam": self.supports_jam(),
            },
        }

        if self.supports_lock():
            payload["state"]["is_locked"] = self.is_locked
            payload["state"]["is_locking"] = self.is_locking
            payload["state"]["is_unlocking"] = self.is_unlocking

        if self.supports_open():
            payload["state"]["is_open"] = self.is_open
            payload["state"]["is_opening"] = self.is_opening
            payload["state"]["is_closing"] = self.is_closing

        if self.supports_jam():
            payload["state"]["is_jammed"] = self.is_jammed

        return payload
