from __future__ import annotations

import asyncio
import logging
import secrets
import string
from typing import TYPE_CHECKING

from passlib.hash import sha512_crypt

from .broker import MqttBridgeBroker
from .client import MqttBridgeClient

if TYPE_CHECKING:
    from ..controller import QolsysController

LOGGER = logging.getLogger(__name__)
logging.getLogger("passlib").setLevel(logging.WARNING)


class MqttBridge:
    def __init__(self, controller: QolsysController) -> None:
        self._controller = controller
        self._broker: MqttBridgeBroker | None = None
        self._client: MqttBridgeClient | None = None
        self._is_running = False
        self._ready_event = asyncio.Event()

        self._version = "1"
        self._mqtt_qos = 1

        self._settings_topic = "settings"
        self._status_topic = "status"
        self._zone_topic = "zone"
        self._partition_topic = "partition"
        self._automation_topic = "automation"
        self._panel_topic = "panel"
        self._scene_topic = "scene"

        self._internal_user = "internal_user"
        self._internal_password = ""

        # Create randon internal_user password
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        self._internal_password = "".join(secrets.choice(alphabet) for _ in range(16))

        # Check if internal_user in allowed_users database
        if self._internal_user in self._controller.settings.mqtt_bridge_broker_allowed_users:
            LOGGER.error(
                "MQTT Bridge - Internal user '%s' already exists in allowed_users. This is a security risk. Please remove the internal user from allowed_users and restart the MQTT Bridge.",
                self._internal_user,
            )
        self._controller.settings.mqtt_bridge_broker_allowed_users[self._internal_user] = sha512_crypt.hash(
            self._internal_password
        )

        if self._controller.settings._mqtt_bridge_broker_enabled:
            self._controller.settings.mqtt_bridge_client_username = self._internal_user
            self._controller.settings.mqtt_bridge_client_password = self._internal_password

    async def wait_for_bridge_start(self, timeout: int = 5) -> None:
        await asyncio.wait_for(self._ready_event.wait(), timeout)

    async def run_bridge(self) -> None:
        if self._is_running:
            LOGGER.warning("MQTT Bridge - Already running")
            return

        self._is_running = True
        self._ready_event.clear()

        try:
            async with asyncio.TaskGroup() as tg:
                LOGGER.debug("MQTT Bridge - Starting")

                # Create MQTT Internal Broker if enabled and not already created
                if self._controller.settings.mqtt_bridge_broker_enabled:
                    if not self._broker:
                        self._broker = MqttBridgeBroker(self)

                    startup_event = asyncio.Event()
                    startup_result: dict[str, bool | Exception] = {"started": False}
                    tg.create_task(self._broker.run_bridge_broker(startup_event, startup_result))
                    await startup_event.wait()
                    result = startup_result.get("started")
                    if result is False:
                        raise RuntimeError("MQTT Bridge Broker failed to start")

                    # If broker is enabled, the client will connect to the local broker
                    self._controller._settings._mqtt_bridge_hostname = self._controller.settings.plugin_ip
                    self._controller._settings._mqtt_bridge_client_username = self._internal_user
                    self._controller._settings._mqtt_bridge_client_password = self._internal_password

                # Run MQTT Bridge Client
                self._client = MqttBridgeClient(self)
                tg.create_task(self._client.run_bridge_client())
                await self._client.wait_for_client_start()
                LOGGER.info("MQTT Bridge - Running")
                self._ready_event.set()

                await asyncio.Future()  # Run until cancelled

        except* asyncio.CancelledError:
            pass

        except* Exception as err:
            LOGGER.error("MQTT Bridge - Failed to start: %s", err)
            raise

        finally:
            self._is_running = False
            LOGGER.debug("MQTT Bridge - Shutdown completed")

    @property
    def panel_unique_id(self) -> str:
        if self._controller.settings.mqtt_bridge_friendly_name != "":
            return self._controller.settings.mqtt_bridge_friendly_name
        return self._controller.panel.unique_id

    @property
    def version(self) -> str:
        return self._version

    @property
    def base_topic(self) -> str:
        return f"{self._controller.settings.mqtt_bridge_root_topic}/v{self.version}/{self.panel_unique_id}"

    @property
    def automation_topic(self) -> str:
        return f"{self.base_topic}/{self._automation_topic}"

    @property
    def partition_topic(self) -> str:
        return f"{self.base_topic}/{self._partition_topic}"

    @property
    def zone_topic(self) -> str:
        return f"{self.base_topic}/{self._zone_topic}"

    @property
    def settings_topic(self) -> str:
        return f"{self.base_topic}/panel/{self._settings_topic}"

    @property
    def status_topic(self) -> str:
        return f"{self.base_topic}/panel/{self._status_topic}"

    @property
    def scene_topic(self) -> str:
        return f"{self.base_topic}/{self._scene_topic}"

    @property
    def automation_command_topic(self) -> str:
        return f"{self.automation_topic}/+/command"

    @property
    def partition_command_topic(self) -> str:
        return f"{self.partition_topic}/+/command"

    @property
    def panel_command_topic(self) -> str:
        return f"{self.base_topic}/panel/command"

    @property
    def command_topics(self) -> list[str]:
        return [
            self.automation_command_topic,
            self.partition_command_topic,
            self.panel_command_topic,
        ]

    @property
    def mqtt_qos(self) -> int:
        return self._mqtt_qos
