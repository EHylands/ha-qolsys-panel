from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..automation.service_lock import LockService
from ..enum_qolsys import QolsysNotification
from ..observable import Event

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice


LOGGER = logging.getLogger(__name__)


class LockServiceZwave(LockService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)

    def supports_lock(self) -> bool:
        return True

    def supports_open(self) -> bool:
        return False

    def supports_jam(self) -> bool:
        return False

    async def lock(self) -> None:
        if self.is_locked:
            LOGGER.debug(
                "%s[%s] LockServiceZwave - lock: already locked",
                self.automation_device.prefix,
                self.endpoint,
            )
            return

        self.is_locking = True
        self.is_unlocking = False
        self.automation_device.notify(
            Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
        )
        self._is_locking = False

        await self.automation_device.controller.commands.zwave.doorlock_set(
            self.automation_device.virtual_node_id, str(self.endpoint), True
        )

    async def unlock(self) -> None:
        if not self.is_locked:
            LOGGER.debug(
                "%s[%s] LockServiceZwave - unlock already unlocked",
                self.automation_device.prefix,
                self.endpoint,
            )
            return

        self.is_locking = False
        self.is_unlocking = True
        self.automation_device.notify(
            Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
        )
        self._is_unlocking = False

        await self.automation_device.controller.commands.zwave.doorlock_set(
            self.automation_device.virtual_node_id, str(self.endpoint), False
        )

    async def open(self) -> None:
        pass

    async def close(self) -> None:
        pass

    def update_automation_service(self) -> None:
        self.is_locked = self.automation_device.status.lower() == "locked"
