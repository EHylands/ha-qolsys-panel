from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..automation.service_valve import ValveService
from ..enum_qolsys import QolsysNotification
from ..enum_zwave import ZwaveCommandClass
from ..observable import Event

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice

LOGGER = logging.getLogger(__name__)


class ValveServiceZwave(ValveService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)

    async def open(self) -> None:
        if not self.is_closed:
            LOGGER.debug("%s - Valve is already open", self.prefix)
            return

        if ZwaveCommandClass.SwitchBinary not in self.automation_device.command_class_list:  # type: ignore[attr-defined]
            LOGGER.error("%s - Valve does not support SwitchBinary command class", self.prefix)
            return

        self.is_closing = False
        self.is_opening = True
        self.automation_device.notify(
            Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
        )
        self._is_opening = False

        await self.automation_device.controller.commands.zwave.switch_binary_set(
            self.automation_device.virtual_node_id, str(self.endpoint), True
        )

    async def close(self) -> None:
        if self.is_closed:
            LOGGER.debug("%s - Valve is already closed", self.prefix)
            return

        if ZwaveCommandClass.SwitchBinary not in self.automation_device.command_class_list:  # type: ignore[attr-defined]
            LOGGER.error("%s - Valve does not support SwitchBinary command class", self.prefix)
            return

        self.is_closing = True
        self.is_opening = False
        self.automation_device.notify(
            Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
        )
        self._is_closing = False

        await self.automation_device.controller.commands.zwave.switch_binary_set(
            self.automation_device.virtual_node_id, str(self.endpoint), False
        )

    async def stop(self) -> None:
        pass

    async def set_position(self, position: int) -> None:
        pass

    def supports_open(self) -> bool:
        return True

    def supports_close(self) -> bool:
        return True

    def supports_stop(self) -> bool:
        return False

    def supports_position(self) -> bool:
        return False

    def update_automation_service(self) -> None:
        self.is_closed = self.automation_device.status.lower() == "closed"
