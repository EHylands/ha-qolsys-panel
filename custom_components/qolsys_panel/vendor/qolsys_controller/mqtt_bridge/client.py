import asyncio
import json
import logging
import ssl
from typing import TYPE_CHECKING, Any

import aiomqtt
from aiomqtt import ProtocolVersion

from ..automation.device import QolsysAutomationDevice
from ..automation.service import AutomationService
from ..automation.service_cover import CoverService
from ..automation.service_light import LightService
from ..automation.service_lock import LockService
from ..automation.service_outlet import OutletService
from ..automation.service_siren import SirenService
from ..automation.service_thermostat import ThermostatService
from ..automation.service_valve import ValveService
from ..enum_qolsys import (
    PartitionArmingType,
    QolsysFanMode,
    QolsysHvacMode,
    QolsysNotification,
)
from ..observable import Event
from ..partition import QolsysPartition

LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..mqtt_bridge.bridge import MqttBridge


class MqttBridgeClient:
    def __init__(self, bridge: "MqttBridge") -> None:
        self._bridge = bridge
        self._ready_event = asyncio.Event()
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=1000)
        self._registered = False
        self._is_running = False
        self._client: aiomqtt.Client | None = None
        self._reconnect_attempt: int = 0

    async def wait_for_client_start(self, timeout: int = 10) -> None:
        await asyncio.wait_for(self._ready_event.wait(), timeout)

    def handle_event(self, event: Event) -> None:
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            LOGGER.debug("MQTT Bridge Client: Queue is full. Dropping event: %s", event)

    async def run_bridge_client(self) -> None:
        LOGGER.info("MQTT Bridge Client - Starting")
        self._ready_event.clear()
        if self._is_running:
            LOGGER.warning("MQTT Bridge Client - Already running")
            self._ready_event.set()
            return
        self._is_running = True
        self._reconnect_attempt = 0
        try:
            while True:
                reconnect = False
                LOGGER.debug(
                    "MQTT Bridge Client - Connecting to %s:%s",
                    self._bridge._controller.settings.mqtt_bridge_hostname,
                    self._bridge._controller.settings.mqtt_bridge_port,
                )

                try:
                    # Audit M8: this used to be CERT_NONE, so any host on the
                    # network could impersonate the broker. Pin the broker
                    # certificate created by create_mqtt_bridge_certificates.
                    # Hostname checking stays off: that certificate has no SAN
                    # and the bridge is reached by address.
                    tls_context = ssl.create_default_context(
                        cafile=str(self._bridge._controller._pki.mqtt_bridge_cer_file_path)
                    )
                    tls_context.check_hostname = False
                    tls_context.verify_mode = ssl.CERT_REQUIRED

                    async with aiomqtt.Client(
                        username=self._bridge._controller.settings.mqtt_bridge_client_username,
                        password=self._bridge._controller.settings.mqtt_bridge_client_password,
                        protocol=ProtocolVersion.V311,
                        hostname=self._bridge._controller.settings.mqtt_bridge_hostname,
                        port=self._bridge._controller.settings.mqtt_bridge_port,
                        tls_context=tls_context if self._bridge._controller.settings.mqtt_bridge_tls_enabled else None,
                        identifier=self._bridge._controller.settings._mqtt_bridge_client_id,
                        keepalive=self._bridge._controller.settings.mqtt_timeout,
                    ) as self._client:
                        # Subscribe
                        for topic in self._bridge.command_topics:
                            LOGGER.debug("MQTT Bridge Client - Subscribing to topic: %s", topic)
                            await self._client.subscribe(topic, qos=self._bridge.mqtt_qos)

                        # Register events ONCE
                        if not self._registered:
                            self._register_events()
                            self._registered = True

                        # Refresh state to publish current values on startup
                        self._refresh_state()

                        # MQTT Bridge Client is connected and running
                        if not self._ready_event.is_set():
                            self._ready_event.set()

                        # Run listener + publisher concurrently
                        async with asyncio.TaskGroup() as tg:
                            tg.create_task(self._listener(self._client))
                            tg.create_task(self._publisher(self._client))
                            LOGGER.info("MQTT Bridge Client - Running")

                            await asyncio.Future()  # Run until cancelled

                except* asyncio.CancelledError:
                    LOGGER.debug("MQTT Bridge Client - Shutting down ...")
                    raise

                except* aiomqtt.MqttError as err:
                    LOGGER.debug("MQTT Bridge Client - Connection error: %s", err)
                    reconnect = True

                except* Exception as err:
                    for exc in err.exceptions:
                        LOGGER.exception("MQTT Bridge Client - Supervisor detected failure: %r", exc)
                    raise

                finally:
                    if reconnect:
                        MAX_RECONNECT_DELAY = 300
                        delay = min(1 * (2**self._reconnect_attempt), MAX_RECONNECT_DELAY)
                        self._reconnect_attempt += 1

                        LOGGER.debug(
                            "MQTT Bridge Client - Reconnecting in %s seconds (attempt %d)",
                            delay,
                            self._reconnect_attempt,
                        )
                        await asyncio.sleep(delay)
                    else:
                        LOGGER.info("MQTT Bridge Client - Shutdown completed")
        finally:
            self._is_running = False

    async def _listener(self, client: aiomqtt.Client) -> None:
        async for message in client.messages:
            if message.topic.matches(self._bridge.automation_command_topic):
                await self._handle_automation_command(
                    self._extract_id_from_topic(str(message.topic)), message.payload.decode(errors="ignore")
                )

            if message.topic.matches(self._bridge.partition_command_topic):
                await self._handle_partition_command(
                    self._extract_id_from_topic(str(message.topic)), message.payload.decode(errors="ignore")
                )

            if message.topic.matches(self._bridge.panel_command_topic):
                await self._handle_panel_command(message.payload.decode(errors="ignore"))

    async def _publisher(self, client: aiomqtt.Client) -> None:
        try:
            event: Event | None = None
            while True:
                event = await self._queue.get()
                payload = json.dumps(event.data)

                id = event.data.get("id")
                if event.type == QolsysNotification.ZONE_UPDATE:
                    topic = f"{self._bridge.zone_topic}/{id}"
                elif event.type == QolsysNotification.PARTITION_UPDATE:
                    topic = f"{self._bridge.partition_topic}/{id}"
                elif event.type == QolsysNotification.AUTOMATION_UPDATE:
                    topic = f"{self._bridge.automation_topic}/{id}"
                elif event.type == QolsysNotification.PANEL_STATUS_UPDATE:
                    topic = f"{self._bridge.status_topic}"
                elif event.type == QolsysNotification.PANEL_SETTINGS_UPDATE:
                    topic = f"{self._bridge.settings_topic}"
                elif event.type == QolsysNotification.SCENE_UPDATE:
                    topic = f"{self._bridge.scene_topic}/{id}"
                else:
                    continue

                if not client:
                    LOGGER.warning("MQTT client not available to publish event")
                    continue

                await client.publish(topic, payload, qos=self._bridge.mqtt_qos, retain=True)

        except asyncio.CancelledError:
            raise

        except aiomqtt.MqttError:
            if event is not None:
                LOGGER.exception("MQTT Panel Client - error while publishing event %s", event)
            raise

        except Exception as err:
            LOGGER.exception("MQTT Panel Client - publish task error: %s", err)
            raise

    def _refresh_state(self) -> None:
        LOGGER.debug("MQTT Bridge Client - Refreshing state ...")
        for zone in self._bridge._controller.state.zones:
            self.handle_event(Event(QolsysNotification.ZONE_UPDATE, zone, zone.to_dict_event()))

        for partition in self._bridge._controller.state.partitions:
            self.handle_event(Event(QolsysNotification.PARTITION_UPDATE, partition, partition.to_dict_event()))

        for autdev in self._bridge._controller.state.automation_devices:
            self.handle_event(Event(QolsysNotification.AUTOMATION_UPDATE, autdev, autdev.to_dict_event()))

        for scene in self._bridge._controller.state.scenes:
            self.handle_event(Event(QolsysNotification.SCENE_UPDATE, scene, scene.to_dict_event()))

        # Panel status initial state update
        self.handle_event(
            Event(
                QolsysNotification.PANEL_STATUS_UPDATE,
                self._bridge._controller.panel,
                self._bridge._controller._to_event_dict(),
            )
        )

        # Panel settings initial state update
        self.handle_event(
            Event(
                QolsysNotification.PANEL_SETTINGS_UPDATE,
                self._bridge._controller.panel,
                self._bridge._controller.panel.to_event_dict(),
            )
        )

    def _register_events(self) -> None:
        LOGGER.debug("MQTT Bridge Client - Registering events ...")

        for zone in self._bridge._controller.state.zones:
            zone.register(QolsysNotification.ZONE_UPDATE, self.handle_event)

        for partition in self._bridge._controller.state.partitions:
            partition.register(QolsysNotification.PARTITION_UPDATE, self.handle_event)

        for autdev in self._bridge._controller.state.automation_devices:
            autdev.register(QolsysNotification.AUTOMATION_UPDATE, self.handle_event)

        for scene in self._bridge._controller.state.scenes:
            scene.register(QolsysNotification.SCENE_UPDATE, self.handle_event)

        self._bridge._controller.state.register(QolsysNotification.PANEL_STATUS_UPDATE, self.handle_event)
        self._bridge._controller.state.register(QolsysNotification.PANEL_SETTINGS_UPDATE, self.handle_event)

    async def _get_service(
        self, device: QolsysAutomationDevice, service_cls: Any, endpoint: int, data: dict[str, Any]
    ) -> AutomationService | None:
        service: AutomationService | None = device.service_get(service_cls, endpoint)

        if not isinstance(service, service_cls):
            await self._handle_error("service_not_found", data, service_cls.__name__)
            return None

        if not isinstance(service, AutomationService):
            await self._handle_error("service_not_found", data, service_cls.__name__)
            return None

        return service

    async def _require_field(self, data: dict[str, Any], field: str, error_key: str) -> Any:
        value = data.get(field)
        if value is None:
            await self._handle_error(error_key, data)
            return None
        return value

    def _get_partition_command_map(self) -> dict[str, Any]:
        return {
            "DISARM": self._cmd_disarm,
            "ARM_STAY": self._cmd_arm_stay,
            "ARM_AWAY": self._cmd_arm_away,
            "ARM_NIGHT": self._cmd_arm_night,
            "TRIGGER_POLICE_EMERGENCY_SILENT": self._cmd_trigger_police_emergency_silent,
            "TRIGGER_POLICE_EMERGENCY": self._cmd_trigger_police_emergency,
            "TRIGGER_AUXILIARY_EMERGENCY": self._cmd_trigger_auxiliary_emergency,
            "TRIGGER_AUXILIARY_EMERGENCY_SILENT": self._cmd_trigger_auxiliary_emergency_silent,
            "TRIGGER_FIRE_EMERGENCY": self._cmd_trigger_fire_emergency,
        }

    def _get_automation_command_map(self) -> dict[str, Any]:
        return {
            "LIGHT_ON": self._cmd_light_on,
            "LIGHT_OFF": self._cmd_light_off,
            "LIGHT_LEVEL": self._cmd_light_level,
            "LOCK": self._cmd_lock,
            "UNLOCK": self._cmd_unlock,
            "COVER_OPEN": self._cmd_cover_open,
            "COVER_CLOSE": self._cmd_cover_close,
            "COVER_POSITION": self._cmd_cover_position,
            "SIREN_ON": self._cmd_siren_on,
            "SIREN_OFF": self._cmd_siren_off,
            "OUTLET_ON": self._cmd_outlet_on,
            "OUTLET_OFF": self._cmd_outlet_off,
            "VALVE_OPEN": self._cmd_valve_open,
            "VALVE_CLOSE": self._cmd_valve_close,
            "VALVE_STOP": self._cmd_valve_stop,
            "VALVE_POSITION": self._cmd_valve_position,
            "THERMOSTAT_FAN_MODE": self._cmd_thermostat_fan_mode,
            "THERMOSTAT_MODE": self._cmd_thermostat_mode,
            "THERMOSTAT_HEAT": self._cmd_thermostat_heat,
            "THERMOSTAT_COOL": self._cmd_thermostat_cool,
        }

    async def _handle_automation_command(self, topic_virtual_node_id: str | None, payload: str) -> None:
        # Decode JSON
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            LOGGER.error("MQTT Bridge Client: Invalid JSON payload: %s", payload)
            return

        virtual_node_id: int = data.get("virtual_node_id")
        command: str = (data.get("command") or "").upper()
        endpoint: int = data.get("endpoint")

        # Check if topic virtual_node_id matches payload virtual_node_id
        if topic_virtual_node_id is None:
            LOGGER.error("MQTT Bridge Client: Missing virtual_node_id in topic")
            await self._handle_error("invalid_virtual_node_id", data)
            return

        if virtual_node_id is not None and str(virtual_node_id) != topic_virtual_node_id:
            LOGGER.error(
                "MQTT Bridge Client - virtual_node_id in topic (%s) does not match virtual_node_id in payload (%s)",
                topic_virtual_node_id,
                virtual_node_id,
            )
            await self._handle_error("invalid_virtual_node_id", data)
            return

        if virtual_node_id is None:
            LOGGER.error("MQTT Bridge Client - Missing virtual_id in payload")
            await self._handle_error("invalid_virtual_node_id", data)
            return

        if endpoint is None:
            LOGGER.error("MQTT Bridge Client - Missing endpoint in payload")
            await self._handle_error("endpoint_missing", data)
            return

        automation_device = self._bridge._controller.state.automation_device(str(virtual_node_id))
        if automation_device is None:
            LOGGER.error("MQTT Bridge Client - Automation device not found for virtual_node_id: %s", virtual_node_id)
            await self._handle_error("automation_device_not_found", data)
            return

        automation_command_map = self._get_automation_command_map()

        handler = automation_command_map.get(command)
        if not handler:
            await self._handle_error("invalid_automation_command", data)
            return

        await handler(automation_device, endpoint, data)

    def _extract_id_from_topic(self, topic: str) -> str | None:
        parts = str(topic).split("/")
        if len(parts) < 3:
            return None
        return parts[-2]

    async def _handle_panel_command(self, payload: str) -> None:
        # Decode JSON
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            LOGGER.error("MQTT Bridge Client - Invalid JSON payload: %s", payload)
            return

        command: str = (data.get("command") or "").upper()

        match command:
            case "PANEL_SPEAK":
                message = await self._require_field(data, "message", "panel_speak_message_missing")
                if not message:
                    return
                await self._bridge._controller.commands.panel.speak(message)
                await self._send_success(data)

            case "EXECUTE_SCENE":
                scene_id = await self._require_field(data, "scene_id", "invalid_scene_id")
                if not scene_id:
                    return
                await self._bridge._controller.commands.panel.execute_scene(str(scene_id))
                await self._send_success(data)

    async def _handle_partition_command(self, topic_partition_id: str | None, payload: str) -> None:
        # Decode JSON
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            LOGGER.error("MQTT Bridge Client - Invalid JSON payload: %s", payload)
            return

        command: str = (data.get("command") or "").upper()
        partition_id = await self._require_field(data, "partition_id", "invalid_partition_id")

        if not partition_id:
            return

        if topic_partition_id is not None and str(topic_partition_id) != str(partition_id):
            LOGGER.error(
                "MQTT Bridge Client - partition_id in topic (%s) does not match partition_id in payload (%s)",
                topic_partition_id,
                partition_id,
            )
            await self._handle_error("invalid_partition_id", data)
            return

        partition = self._bridge._controller.state.partition(str(partition_id))
        if partition is None:
            LOGGER.error("MQTT Bridge Client - Partition not found for partition_id: %s", partition_id)
            await self._handle_error("invalid_partition_id", data)
            return

        partition_command_map = self._get_partition_command_map()
        handler = partition_command_map.get(command)
        if not handler:
            await self._handle_error("invalid_partition_command", data)
            return

        await handler(partition, data)

    async def _send_success(self, data: dict[str, Any]) -> None:
        if not data.get("response_topic"):
            LOGGER.debug("MQTT Bridge Clien - No response_topic provided, skipping success response")
            return

        if not self._client:
            LOGGER.error("MQTT client not available to publish success response")
            return

        await self._client.publish(
            data["response_topic"],
            json.dumps({"success": True, "command_id": data.get("command_id")}),
            qos=self._bridge.mqtt_qos,
            retain=False,
        )

    async def _handle_error(self, error: str, data: dict[str, Any], service_type: str | None = None) -> None:
        response_dict: dict[str, Any] = {}

        command: str = (data.get("command") or "").upper()
        virtual_node_id: int | None = data.get("virtual_node_id")
        endpoint: int | None = data.get("endpoint")
        command_id: str | None = data.get("command_id")
        response_topic: str | None = data.get("response_topic")

        match error:
            case "panel_speak_message_missing":
                response_dict = {
                    "success": False,
                    "error": "panel_speak_message_missing",
                    "error_msg": "Panel Speak Command - Missing message field in payload",
                    "command_id": command_id,
                }
            case "invalid_scene_id":
                response_dict = {
                    "success": False,
                    "error": "scene_id_missing",
                    "error_msg": "Execute Scene Command - Invalid scene_id field in payload",
                    "command_id": command_id,
                }
            case "invalid_partition_id":
                response_dict = {
                    "success": False,
                    "error": "invalid_partition_id",
                    "error_msg": f"Partition Command - Invalid or missing partition_id: {data.get('partition_id')}",
                    "command_id": command_id,
                }
            case "invalid_partition_command":
                response_dict = {
                    "success": False,
                    "error": "invalid_partition_command",
                    "error_msg": f"Partition Command - Invalid command: {command}",
                    "command_id": command_id,
                }
            case "invalid_automation_command":
                response_dict = {
                    "success": False,
                    "error": "invalid_automation_command",
                    "error_msg": f"Automation Command - Invalid command: {command}",
                    "command_id": command_id,
                }

            case "light_level_missing":
                response_dict = {
                    "success": False,
                    "error": "light_level_missing",
                    "error_msg": f"Automation Command - Missing level for {command} command",
                    "command_id": command_id,
                }

            case "cover_position_missing":
                response_dict = {
                    "success": False,
                    "error": "cover_position_missing",
                    "error_msg": f"Automation Command - Missing position for {command} command",
                    "command_id": command_id,
                }

            case "valve_position_missing":
                response_dict = {
                    "success": False,
                    "error": "valve_position_missing",
                    "error_msg": f"Automation Command - Missing position for {command} command",
                    "command_id": command_id,
                }

            case "operation_not_supported_by_service":
                response_dict = {
                    "success": False,
                    "error": "operation_not_supported_by_service",
                    "error_msg": f"Automation Command - {service_type} does not support {command} for virtual_node_id: {virtual_node_id}, endpoint: {endpoint}",
                    "command_id": command_id,
                }

            case "endpoint_missing":
                response_dict = {
                    "success": False,
                    "error": "endpoint_missing",
                    "error_msg": "Automation Command - Missing endpoint in payload",
                    "command_id": command_id,
                }

            case "automation_device_not_found":
                response_dict = {
                    "success": False,
                    "error": "invalid_automation_device",
                    "error_msg": f"Automation Command - Automation device not found for virtual_node_id: {virtual_node_id}",
                    "command_id": command_id,
                }

            case "service_not_found":
                response_dict = {
                    "success": False,
                    "error": "service_not_found",
                    "error_msg": f"Automation Command - {service_type} not found for virtual_node_id: {virtual_node_id}, endpoint: {endpoint}",
                    "command_id": command_id,
                }

            case "invalid_virtual_node_id":
                response_dict = {
                    "success": False,
                    "error": "invalid_virtual_node_id",
                    "error_msg": "virtual_node_id mismatch between topic and payload",
                    "command_id": command_id,
                }

            case "invalid_thermostat_mode":
                response_dict = {
                    "success": False,
                    "error": "invalid_thermostat_mode",
                    "error_msg": f"Automation Command - Invalid thermostat mode: {data.get('mode')}",
                    "command_id": command_id,
                }

            case "invalid_thermostat_fan_mode":
                response_dict = {
                    "success": False,
                    "error": "invalid_thermostat_fan_mode",
                    "error_msg": f"Automation Command - Invalid thermostat fan mode: {data.get('fan_mode')}",
                    "command_id": command_id,
                }

            case "user_code_required":
                response_dict = {
                    "success": False,
                    "error": "user_code_required",
                    "error_msg": "Partition Command - A user_code is required to disarm",
                    "command_id": command_id,
                }

            case "invalid_user_code":
                response_dict = {
                    "success": False,
                    "error": "invalid_user_code",
                    "error_msg": "Partition Command - Invalid user_code",
                    "command_id": command_id,
                }

            case "thermostat_temp_missing":
                response_dict = {
                    "success": False,
                    "error": "thermostat_temp_missing",
                    "error_msg": f"Automation Command - Missing temperature for {command} command",
                    "command_id": command_id,
                }

        LOGGER.debug("MQTT Bridge Client - Publishing error response to topic %s: %s", response_topic, response_dict)

        if not self._client:
            LOGGER.error("MQTT client not available to publish error")
            return

        if not response_topic:
            LOGGER.error("No response_topic provided, cannot send error response")
            return

        await self._client.publish(
            topic=response_topic, payload=json.dumps(response_dict), qos=self._bridge.mqtt_qos, retain=False
        )

    async def _cmd_light_on(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        service = await self._get_service(device, LightService, endpoint, data)
        if isinstance(service, LightService):
            await service.turn_on()
            await self._send_success(data)

    async def _cmd_light_off(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        service = await self._get_service(device, LightService, endpoint, data)
        if isinstance(service, LightService):
            await service.turn_off()
            await self._send_success(data)

    async def _cmd_light_level(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        level = await self._require_field(data, "level", "light_level_missing")
        if level is None:
            return

        service = await self._get_service(device, LightService, endpoint, data)
        if isinstance(service, LightService):
            if not service.supports_level():
                await self._handle_error("operation_not_supported_by_service", data, "LightService")
                return
            await service.set_level(level)
            await self._send_success(data)

    async def _cmd_lock(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        service = await self._get_service(device, LockService, endpoint, data)
        if isinstance(service, LockService):
            if not service.supports_lock():
                await self._handle_error("operation_not_supported_by_service", data, "LockService")
                return

            await service.lock()
            await self._send_success(data)

    async def _cmd_unlock(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        service = await self._get_service(device, LockService, endpoint, data)
        if isinstance(service, LockService):
            if not service.supports_lock():
                await self._handle_error("operation_not_supported_by_service", data, "LockService")
                return

            await service.unlock()
            await self._send_success(data)

    async def _cmd_cover_open(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        service = await self._get_service(device, CoverService, endpoint, data)
        if isinstance(service, CoverService):
            if not service.supports_open():
                await self._handle_error("operation_not_supported_by_service", data, "CoverService")
                return

            await service.open()
            await self._send_success(data)

    async def _cmd_cover_close(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        service = await self._get_service(device, CoverService, endpoint, data)
        if isinstance(service, CoverService):
            if not service.supports_close():
                await self._handle_error("operation_not_supported_by_service", data, "CoverService")
                return

            await service.close()
            await self._send_success(data)

    async def _cmd_cover_position(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        pos = await self._require_field(data, "position", "cover_position_missing")
        if pos is None:
            return

        service = await self._get_service(device, CoverService, endpoint, data)
        if isinstance(service, CoverService):
            if not service.supports_position():
                await self._handle_error("operation_not_supported_by_service", data, "CoverService")
                return

            await service.set_current_position(pos)
            await self._send_success(data)

    async def _cmd_siren_on(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        service = await self._get_service(device, SirenService, endpoint, data)
        if isinstance(service, SirenService):
            await service.turn_on()
            await self._send_success(data)

    async def _cmd_siren_off(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        service = await self._get_service(device, SirenService, endpoint, data)
        if isinstance(service, SirenService):
            await service.turn_off()
            await self._send_success(data)

    async def _cmd_outlet_on(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        service = await self._get_service(device, OutletService, endpoint, data)
        if isinstance(service, OutletService):
            await service.turn_on()
            await self._send_success(data)

    async def _cmd_outlet_off(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        service = await self._get_service(device, OutletService, endpoint, data)
        if isinstance(service, OutletService):
            await service.turn_off()
            await self._send_success(data)

    async def _cmd_valve_open(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        service = await self._get_service(device, ValveService, endpoint, data)
        if isinstance(service, ValveService):
            if not service.supports_open():
                await self._handle_error("operation_not_supported_by_service", data, "ValveService")
                return

            await service.open()
            await self._send_success(data)

    async def _cmd_valve_close(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        service = await self._get_service(device, ValveService, endpoint, data)
        if isinstance(service, ValveService):
            if not service.supports_close():
                await self._handle_error("operation_not_supported_by_service", data, "ValveService")
                return

            await service.close()
            await self._send_success(data)

    async def _cmd_valve_stop(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        service = await self._get_service(device, ValveService, endpoint, data)
        if isinstance(service, ValveService):
            if not service.supports_stop():
                await self._handle_error("operation_not_supported_by_service", data, "ValveService")
                return

            await service.stop()
            await self._send_success(data)

    async def _cmd_valve_position(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        pos = await self._require_field(data, "position", "valve_position_missing")
        if pos is None:
            return

        service = await self._get_service(device, ValveService, endpoint, data)
        if isinstance(service, ValveService):
            if not service.supports_position():
                await self._handle_error("operation_not_supported_by_service", data, "ValveService")
                return

            await service.set_position(pos)
            await self._send_success(data)

    async def _cmd_thermostat_mode(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        mode = await self._require_field(data, "mode", "invalid_thermostat_mode")
        if mode is None:
            return

        if mode not in [x.name for x in QolsysHvacMode]:
            await self._handle_error("invalid_thermostat_mode", data)
            return

        service = await self._get_service(device, ThermostatService, endpoint, data)
        if isinstance(service, ThermostatService):
            await service.set_hvac_mode(QolsysHvacMode[mode])
            await self._send_success(data)

    async def _cmd_thermostat_heat(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        temp = await self._require_field(data, "temperature", "thermostat_temp_missing")
        if temp is None:
            return

        service = await self._get_service(device, ThermostatService, endpoint, data)
        if isinstance(service, ThermostatService):
            if not service.supports_target_temperature():
                await self._handle_error("operation_not_supported_by_service", data, "ThermostatService")
                return

            await service.set_temperature(temp, QolsysHvacMode.HEAT)
            await self._send_success(data)

    async def _cmd_thermostat_cool(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        temp = await self._require_field(data, "temperature", "thermostat_temp_missing")
        if temp is None:
            return

        service = await self._get_service(device, ThermostatService, endpoint, data)
        if isinstance(service, ThermostatService):
            if not service.supports_target_temperature():
                await self._handle_error("operation_not_supported_by_service", data, "ThermostatService")
                return

            await service.set_temperature(temp, QolsysHvacMode.COOL)
            await self._send_success(data)

    async def _cmd_thermostat_fan_mode(self, device: QolsysAutomationDevice, endpoint: int, data: dict[str, Any]) -> None:
        fan_mode = await self._require_field(data, "fan_mode", "invalid_thermostat_fan_mode")
        if fan_mode is None:
            return

        if fan_mode not in [x.name for x in QolsysFanMode]:
            await self._handle_error("invalid_thermostat_fan_mode", data)
            return

        service = await self._get_service(device, ThermostatService, endpoint, data)
        if isinstance(service, ThermostatService):
            if not service.supports_fan_mode():
                await self._handle_error("operation_not_supported_by_service", data, "ThermostatService")
                return

            await service.set_fan_mode(QolsysFanMode[fan_mode])
            await self._send_success(data)

    async def _cmd_disarm(self, partition: QolsysPartition, data: dict[str, Any]) -> None:
        user_code: str = data.get("user_code", "")
        silent_disarm: bool = data.get("silent_disarm", False)

        # Audit M8: anyone able to publish to the bridge topic used to disarm the
        # house with an empty payload field. Refuse without a code, and always
        # validate it, whatever check_user_code_on_disarm says - a bridge client
        # is not the Home Assistant user interface.
        if not user_code:
            LOGGER.warning("MQTT Bridge Client - Disarm refused: no user_code in payload")
            await self._handle_error("user_code_required", data)
            return

        if await asyncio.to_thread(self._bridge._controller.panel.check_user, user_code) == -1:
            LOGGER.warning("MQTT Bridge Client - Disarm refused: unknown user_code")
            await self._handle_error("invalid_user_code", data)
            return

        await self._bridge._controller.commands.panel.disarm(partition.id, user_code, silent_disarm)
        await self._send_success(data)

    async def _cmd_arm_stay(self, partition: QolsysPartition, data: dict[str, Any]) -> None:
        user_code: str = data.get("user_code", "")
        exit_delay: bool = data.get("exit_delay", True)
        exit_sounds: bool = data.get("exit_sounds", True)
        instant_arm: bool = data.get("instant_arm", False)
        await self._bridge._controller.commands.panel.arm(
            partition.id, PartitionArmingType.ARM_STAY, user_code, exit_delay, exit_sounds, instant_arm
        )
        await self._send_success(data)

    async def _cmd_arm_away(self, partition: QolsysPartition, data: dict[str, Any]) -> None:
        user_code: str = data.get("user_code", "")
        exit_delay: bool = data.get("exit_delay", True)
        exit_sounds: bool = data.get("exit_sounds", True)
        instant_arm: bool = data.get("instant_arm", False)
        await self._bridge._controller.commands.panel.arm(
            partition.id, PartitionArmingType.ARM_AWAY, user_code, exit_delay, exit_sounds, instant_arm
        )
        await self._send_success(data)

    async def _cmd_arm_night(self, partition: QolsysPartition, data: dict[str, Any]) -> None:
        user_code: str = data.get("user_code", "")
        exit_delay: bool = data.get("exit_delay", True)
        exit_sounds: bool = data.get("exit_sounds", True)
        instant_arm: bool = data.get("instant_arm", False)
        await self._bridge._controller.commands.panel.arm(
            partition.id, PartitionArmingType.ARM_NIGHT, user_code, exit_delay, exit_sounds, instant_arm
        )
        await self._send_success(data)

    async def _cmd_trigger_police_emergency_silent(self, partition: QolsysPartition, data: dict[str, Any]) -> None:
        await self._bridge._controller.commands.panel.trigger_police(partition.id, silent=True)
        await self._send_success(data)

    async def _cmd_trigger_police_emergency(self, partition: QolsysPartition, data: dict[str, Any]) -> None:
        await self._bridge._controller.commands.panel.trigger_police(partition.id, silent=False)
        await self._send_success(data)

    async def _cmd_trigger_auxiliary_emergency(self, partition: QolsysPartition, data: dict[str, Any]) -> None:
        await self._bridge._controller.commands.panel.trigger_auxilliary(partition.id, silent=False)
        await self._send_success(data)

    async def _cmd_trigger_auxiliary_emergency_silent(self, partition: QolsysPartition, data: dict[str, Any]) -> None:
        await self._bridge._controller.commands.panel.trigger_auxilliary(partition.id, silent=True)
        await self._send_success(data)

    async def _cmd_trigger_fire_emergency(self, partition: QolsysPartition, data: dict[str, Any]) -> None:
        await self._bridge._controller.commands.panel.trigger_fire(partition.id)
        await self._send_success(data)
