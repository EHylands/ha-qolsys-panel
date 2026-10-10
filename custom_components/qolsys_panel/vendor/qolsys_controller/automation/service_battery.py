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


class BatteryService(AutomationService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)
        self._service_name = "BatteryService"
        self._battery_level: int | None = None
        self._battery_low: bool = False
        self._is_disabled: bool = False

    @abstractmethod
    def supports_battery_low(self) -> bool:
        pass

    @abstractmethod
    def supports_battery_level(self) -> bool:
        pass

    @property
    def is_disabled(self) -> bool:
        return not self.supports_battery_level() and not self.supports_battery_low()

    @property
    def battery_level(self) -> int | None:
        return self._battery_level

    @battery_level.setter
    def battery_level(self, value: int) -> None:
        if not self.supports_battery_level():
            self._battery_level = None
            return

        if not (0 <= value <= 100):
            LOGGER.error("%s - battery_level: invalid value: %s", self.prefix, value)
            self._battery_level = None
            return

        if self._battery_level != value:
            self._battery_level = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - battery_level: %s", self.prefix, value)

    @property
    def battery_low(self) -> bool:
        return self._battery_low

    @battery_low.setter
    def battery_low(self, value: bool) -> None:
        if not self.supports_battery_low():
            return

        if self._battery_low != value:
            self._battery_low = value
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )
            LOGGER.debug("%s - battery_low: %s", self.prefix, value)

    def info(self) -> list[str]:
        str = []

        # Return disabled if both battery level and low are not supported
        if not self.supports_battery_level() and not self.supports_battery_low():
            str.append(f"{self.prefix} - Disabled")
            return str

        str.append(f"{self.prefix} - supports_battery_level: {self.supports_battery_level()}")
        str.append(f"{self.prefix} - supports_battery_low: {self.supports_battery_low()}")

        if self.supports_battery_level():
            str.append(f"{self.prefix} - battery_level: {self.battery_level}%")
            return str
        if self.supports_battery_low():
            str.append(f"{self.prefix} - battery_low: {self.battery_low}")
            return str

        return str

    def to_dict_event(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "service_type": self.service_name,
            "state": {
                "is_disabled": self.is_disabled,
            },
            "attributes": {
                "endpoint": self.endpoint,
            },
            "capabilities": {
                "supports_battery_level": self.supports_battery_level(),
                "supports_battery_low": self.supports_battery_low(),
            },
        }

        if self.supports_battery_level():
            payload["state"]["battery_level"] = self.battery_level

        if self.supports_battery_low():
            payload["state"]["battery_low"] = self.battery_low

        return payload
