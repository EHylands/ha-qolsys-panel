from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..errors import InvalidVirtualNodeError
from ..mqtt_command import MQTTCommand_Automation

if TYPE_CHECKING:
    from ..controller import QolsysController

LOGGER = logging.getLogger(__name__)


class AutomationCommands:
    def __init__(self, controller: QolsysController) -> None:
        self._controller = controller

    async def door_lock(self, virtual_node_id: int, endpoint: int) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending automation_door_lock command - Node(%s)(%s)", virtual_node_id, endpoint)

        # Check if virtual_node_id exist
        virtual_node = self._controller.state.automation_device(str(virtual_node_id))
        if not virtual_node:
            raise InvalidVirtualNodeError(virtual_node_id)

        command = MQTTCommand_Automation(self._controller, virtual_node_id, endpoint, operation_type=5, result="status_Locked")
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving automation_door_lock command: %s", response)
        return response

    async def door_unlock(self, virtual_node_id: int, endpoint: int) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending automation_door_unlock command - Node(%s)(%s)", virtual_node_id, endpoint)

        # Check if virtual_node_id exist
        virtual_node = self._controller.state.automation_device(str(virtual_node_id))
        if not virtual_node:
            raise InvalidVirtualNodeError(virtual_node_id)

        command = MQTTCommand_Automation(
            self._controller, virtual_node_id, endpoint, operation_type=6, result="status_Unlocked"
        )
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving  automation_door_unlock command: %s", response)
        return response

    async def light_on(self, virtual_node_id: int, endpoint: int) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending automation_light_on command - Node(%s)(%s)", virtual_node_id, endpoint)

        # Check if virtual_node_id exist
        virtual_node = self._controller.state.automation_device(str(virtual_node_id))
        if not virtual_node:
            raise InvalidVirtualNodeError(virtual_node_id)

        command = MQTTCommand_Automation(self._controller, virtual_node_id, endpoint, operation_type=1, result="status_On")
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving automation_light_on command")
        return response

    async def light_off(self, virtual_node_id: int, endpoint: int) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending automation_light_off command - Node(%s)(%s)", virtual_node_id, endpoint)

        # Check if virtual_node_id exist
        virtual_node = self._controller.state.automation_device(str(virtual_node_id))
        if not virtual_node:
            raise InvalidVirtualNodeError(virtual_node_id)

        command = MQTTCommand_Automation(self._controller, virtual_node_id, endpoint, operation_type=0, result="status_Off")
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving automation_light_off command")
        return response
