#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import ssl
from datetime import datetime, timezone
from typing import Any

import aiomqtt

from .automation_zwave.device import QolsysAutomationDeviceZwave
from .automation_zwave.service_meter import MeterServiceZwave
from .commands.service import QolsysCommandService
from .mqtt_command import (
    MQTTCommand,
)
from .observable import Event
from .pairing_server import QolsysPairingServer

from .enum_qolsys import (
    VALID_CONTROLLER_TRANSITIONS,
    ControllerState,
    QolsysNotification,
)
from .errors import (
    InvalidControllerStateTransitionError,
    QolsysConfigError,
    QolsysMqttError,
    QolsysOperationTimeoutError,
    QolsysSslError,
)
from .mqtt_bridge.bridge import MqttBridge
from .mqtt_command_queue import QolsysMqttCommandQueue
from .panel import QolsysPanel
from .pki import QolsysPKI
from .settings import QolsysSettings
from .state import QolsysState
from .utils_mqtt import generate_random_mac

LOGGER = logging.getLogger(__name__)


def _first_exception(exc: BaseException) -> BaseException:
    """Return the first leaf exception of a (possibly nested) ExceptionGroup.

    run_forever runs on an asyncio.TaskGroup, which raises (Base)ExceptionGroup.
    Callers want the single meaningful failure (e.g. QolsysConfigError), so the
    group is unwrapped to a plain exception before re-raising from run_forever.
    """
    while isinstance(exc, BaseExceptionGroup):
        exc = exc.exceptions[0]
    return exc


class QolsysController:
    def __init__(self) -> None:
        self._state = QolsysState(self)
        self._settings = QolsysSettings(self)
        self._panel = QolsysPanel(self)
        self._pki = QolsysPKI(settings=self.settings)
        self.commands = QolsysCommandService(self)

        self._controller_state = ControllerState.STOPPED
        self._controller_state_condition = asyncio.Condition()

        self._initial_run: bool = True
        self._is_configured: bool = False
        self._pairing_was_started: bool = False

        # Plugin
        self._mqtt_command_queue = QolsysMqttCommandQueue()
        self._zone_id: str = "1"
        self._pairing_server: QolsysPairingServer | None = None
        self._supervisor_task: asyncio.Task[None] | None = None
        self._shutdown_complete = asyncio.Event()

        # MQTT Panel Client
        self._reconnect_attempt: int = 0
        self._mqtt_publish_queue: asyncio.Queue[MQTTCommand] = asyncio.Queue()

        # MQTT Bridge
        self._mqtt_bridge: MqttBridge | None = None

    @property
    def state(self) -> QolsysState:
        return self._state

    @property
    def panel(self) -> QolsysPanel:
        return self._panel

    @property
    def settings(self) -> QolsysSettings:
        return self._settings

    @property
    def mqtt_command_queue(self) -> QolsysMqttCommandQueue:
        return self._mqtt_command_queue

    ###########################################################################
    # Controller Operations
    ###########################################################################

    async def run_forever(self, reconnect: bool = True, run_once: bool = False, start_pairing: bool = False) -> None:
        LOGGER.debug("Starting Qolsys Controller Operation")
        self._shutdown_complete.clear()
        try:
            async with asyncio.TaskGroup() as tg:
                # Start MQTT Panel Client Supervisor
                self._supervisor_task = tg.create_task(
                    self.run_supervised(reconnect=reconnect, start_pairing=start_pairing),
                    name="MQTT Panel Client Supervisor",
                )
                await self.wait_until_connected()

                # Start MQTT Bridge Broker
                bridge_task = None
                if self.settings.mqtt_bridge_enabled:
                    self._mqtt_bridge = MqttBridge(self)
                    bridge_task = tg.create_task(self._mqtt_bridge.run_bridge(), name="MQTT Bridge")
                    await self._mqtt_bridge.wait_for_bridge_start()

                LOGGER.info("Qolsys Controller Ready for Operation")
                if run_once:
                    LOGGER.debug("Qolsys Controller - Exiting after initialization (run_once=True)")
                    self._supervisor_task.cancel()
                    if bridge_task is not None:
                        bridge_task.cancel()
                    return

                await asyncio.Future()  # Run until cancelled or exception

        except* asyncio.CancelledError:
            await self.set_controller_state(ControllerState.SHUTTING_DOWN)

        except* Exception as eg:
            # asyncio.TaskGroup raises an ExceptionGroup; unwrap to the single
            # meaningful failure so callers get a plain exception (e.g. QolsysConfigError)
            # instead of having to flatten an ExceptionGroup. Log with exc_info=exc so the
            # traceback is the unwrapped exception, not the ExceptionGroup wrapper.
            exc = _first_exception(eg)
            LOGGER.error("Controller - TaskGroup failed with exception: %s", exc, exc_info=exc)
            raise exc from None

        finally:
            if self._pairing_server is not None:
                await self._pairing_server.stop()
                self._pairing_server = None

            try:
                await self.set_controller_state(ControllerState.STOPPED)
            except InvalidControllerStateTransitionError:
                pass

            self._shutdown_complete.set()

    async def stop(self) -> None:
        if self._supervisor_task is None:
            LOGGER.debug("No Supervisor Task to Stop")
            return

        if self._supervisor_task.done():
            LOGGER.debug("Supervisor Task Already Completed")
            return

        LOGGER.debug("Qolsys Controller - Stopping Operation")
        self._supervisor_task.cancel()
        await self._shutdown_complete.wait()

    async def config_task(self, start_pairing: bool) -> None:
        await self.set_controller_state(ControllerState.CONFIGURING)

        # Check and created config_directory
        # Audit M5: is_dir/mkdir/resolve are blocking calls; config_task runs on
        # the event loop, and again on every reconnect where _is_configured is
        # False, so a slow SD card or a network-backed /config stalls all of
        # Home Assistant.
        await asyncio.to_thread(self.settings.check_config_directory, start_pairing)

        # Audit H2: repair permissions on material written by older versions.
        await self._pki.secure_existing_material()

        # Read user file for access codes
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.panel.read_users_file)

        # Config PKI
        if self.settings.auto_discover_pki:
            # Audit M5: os.scandir, same reason.
            if await asyncio.to_thread(self._pki.auto_discover_pki):
                self.settings.random_mac = self._pki.formatted_id()
        else:
            self._pki.set_id(self.settings.random_mac)

        # Check if plugin is paired
        if await self.is_paired():
            LOGGER.debug("Panel is Paired")

        else:
            LOGGER.debug("Panel not paired")

            if not start_pairing:
                LOGGER.debug("Aborting pairing.")
                raise QolsysConfigError("Panel not paired and start_pairing=False")

            await self.start_initial_pairing()

        # Set mqtt_remote_client_id
        self.settings.mqtt_remote_client_id = "qolsys-controller-" + secrets.token_hex(6)
        LOGGER.debug("MQTT Panel Client - Using remoteClientID: %s", self.settings.mqtt_remote_client_id)

        # Everything is configured
        self._is_configured = True

    async def is_paired(self) -> bool:
        return (
            self._pki.id != ""
            and await self._pki.check_key_file()
            and await self._pki.check_cer_file()
            and await self._pki.check_qolsys_cer_file()
            and await self._pki.check_secure_file()
            and self.settings.check_panel_ip()
            and self.settings.check_plugin_ip()
        )

    ###########################################################################
    # MQTT Panel Client
    ###########################################################################

    async def run_supervised(self, reconnect: bool = True, start_pairing: bool = False) -> None:
        self._reconnect_attempt = 0
        while True:
            try:
                # Fresh outbound queue per connection attempt so stale commands
                # from a previous session don't get sent on reconnect.
                self._mqtt_publish_queue = asyncio.Queue()

                # Configure controller
                if not self._is_configured:
                    await self.config_task(start_pairing)

                # Open transport
                await self.set_controller_state(ControllerState.CONNECTING)
                mqtt_panel_client: aiomqtt.Client = await self.mqtt_open_transport_task()

                async with mqtt_panel_client:
                    await mqtt_panel_client.subscribe("iq2meid")
                    await mqtt_panel_client.subscribe("response_" + self.settings.random_mac, qos=self.settings.mqtt_qos)
                    await mqtt_panel_client.subscribe("ZWAVE_RESPONSE", qos=self.settings.mqtt_qos)

                    if self.settings.log_mqtt_messages:
                        await mqtt_panel_client.subscribe("mastermeid", qos=self.settings.mqtt_qos)

                    # Managed Background Tasks
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self.mqtt_listen_task(mqtt_panel_client))
                        tg.create_task(self.mqtt_publish_task(mqtt_panel_client))

                        await asyncio.sleep(2)

                        # Initialize session before background loops
                        await self.mqtt_initialize_session_task()

                        tg.create_task(self.mqtt_ping_task(mqtt_panel_client))
                        tg.create_task(self.mqtt_zwave_meter_update())

                        await self.set_controller_state(ControllerState.CONNECTED)
                        self._reconnect_attempt = 0

                        await asyncio.Future()  # Run until cancelled or exception

            except* asyncio.CancelledError:
                task = asyncio.current_task()
                if task is not None and task.cancelling() > 0:
                    await self.set_controller_state(ControllerState.SHUTTING_DOWN)
                raise

            except* QolsysConfigError as eg:
                # config_task raises a plain QolsysConfigError (not from the inner MQTT
                # TaskGroup); except* wraps it into a group, so unwrap and re-raise the
                # single exception instead of an ExceptionGroup.
                exc = _first_exception(eg)
                LOGGER.error(
                    "MQTT Panel Client - Supervisor detected configuration error: %s",
                    exc,
                    exc_info=exc,
                )
                raise exc from None

            except* aiomqtt.exceptions.MqttError as err:
                for exc in err.exceptions:
                    LOGGER.debug("MQTT Panel Client - Supervisor detected MQTT Error: %r", exc)

                if not reconnect:
                    raise QolsysMqttError from err

            except* QolsysOperationTimeoutError as err:
                LOGGER.debug("MQTT Panel Client - Supervisor detected Operation Time out Error: %r", err)

                if not reconnect:
                    raise QolsysOperationTimeoutError from err

            except* ssl.SSLError as err:
                LOGGER.debug("MQTT Panel Client - Supervisor detected SSL Error: %s", err)
                raise QolsysSslError from err

            except* Exception as err:
                for exc in err.exceptions:
                    LOGGER.exception("MQTT Panel Client - Supervisor detected failure: %r", exc)
                raise

            finally:
                # No notify here: set_controller_state does it, and this ran while
                # the state still read CONNECTED (audit M2).
                self.mqtt_command_queue.fail_all_pending(QolsysMqttError("MQTT Command failed due to disconnection"))

            # Only reached on MqttError with reconnect=True; all other paths raise.
            MAX_RECONNECT_DELAY = 300
            delay = min(1 * (2**self._reconnect_attempt), MAX_RECONNECT_DELAY)
            self._reconnect_attempt += 1

            try:
                await self.set_controller_state(ControllerState.RECONNECTING)
                LOGGER.debug("MQTT Panel Client - Reconnecting in %s seconds (attempt %d)", delay, self._reconnect_attempt)
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                await self.set_controller_state(ControllerState.SHUTTING_DOWN)
                raise

    async def mqtt_open_transport_task(self) -> aiomqtt.Client:
        # Configure TLS context for MQTT connection
        def create_tls_context() -> ssl.SSLContext:
            ctx = ssl.create_default_context(
                purpose=ssl.Purpose.SERVER_AUTH,
                cafile=str(self._pki.qolsys_cer_file_path),
            )
            ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            # Pin the panel certificate: the broker cert must chain to the .qolsys CA
            # saved during pairing. Hostname checking stays off (we connect by IP and
            # the panel cert has no matching SAN), and strict X.509 checks are relaxed
            # because the panel CA lacks a critical BasicConstraints extension.
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
            ctx.load_cert_chain(
                certfile=str(self._pki.secure_file_path),
                keyfile=str(self._pki.key_file_path),
            )
            return ctx

        loop = asyncio.get_running_loop()
        ctx = await loop.run_in_executor(None, create_tls_context)

        return aiomqtt.Client(
            hostname=self.settings.panel_ip,
            port=8883,
            tls_context=ctx,
            tls_insecure=True,
            clean_session=True,
            keepalive=self.settings.mqtt_timeout,
            identifier=self.settings.mqtt_remote_client_id,
        )

    def enqueue_mqtt_command(self, command: MQTTCommand) -> None:
        self._mqtt_publish_queue.put_nowait(command)

    async def mqtt_publish_task(self, client: aiomqtt.Client) -> None:
        LOGGER.debug("MQTT Panel Client - Publish task started")
        command: MQTTCommand | None = None
        while True:
            try:
                command = await self._mqtt_publish_queue.get()
                payload = json.dumps(command._payload)
                await client.publish(command._topic, payload, command._qos)

            except asyncio.CancelledError:
                raise

            except aiomqtt.MqttError:
                if command is not None:
                    LOGGER.exception("MQTT Panel Client - error while publishing command %s", command._eventName)
                    self.mqtt_command_queue.fail_waiter(command._requestID, QolsysMqttError("Failed to publish MQTT command"))
                raise

            except Exception as err:
                LOGGER.exception("MQTT Panel Client - publish task error: %s", err)
                if command is not None:
                    self._mqtt_command_queue.fail_waiter(command._requestID, err)
                raise

    async def mqtt_listen_task(self, client: aiomqtt.Client) -> None:
        LOGGER.debug("MQTT Panel Client - Listen task started")
        async for message in client.messages:
            try:
                data_str = message.payload.decode()
                data_json = json.loads(data_str)
            except (json.JSONDecodeError, UnicodeDecodeError):
                LOGGER.warning("Invalid JSON payload on topic %s: %s", message.topic, message.payload)
                continue

            # Log all MQTT messages for debug purposes if enabled in settings
            if self.settings.log_mqtt_messages:
                LOGGER.debug("MQTT TOPIC: %s\n%s", message.topic, data_str)

            # Panel response to MQTT Commands and Panel Commands to IQ Remote
            if message.topic.matches("response_" + self.settings.random_mac):
                await self._mqtt_command_queue.handle_response(data_json)

            # Panel updates to IQ2MEID database
            elif message.topic.matches("iq2meid"):
                self.panel.parse_iq2meid_message(data_json)

            # Panel Z-Wave response
            elif message.topic.matches("ZWAVE_RESPONSE"):
                self.panel.parse_zwave_message(data_json)

    async def mqtt_initialize_session_task(self) -> None:
        LOGGER.debug("MQTT Panel Client - Initializing session")
        response_connect = await self.commands.panel.connect()
        self.panel.imei = response_connect.get("master_imei", "")
        self.panel.product_type = response_connect.get("primary_product_type", "")

        await self.commands.panel.pingevent()
        await self.commands.panel.pair_status_request()

        response_database = await self.commands.panel.sync_database()
        await self.panel.load_database(response_database.get("fulldbdata"))

        if self._pairing_was_started:
            LOGGER.debug("Plugin Pairing Completed ")
            await self._pki.pairing_resume_pki_set(False)

        if self._initial_run:
            self._initial_run = False
            self.panel.dump()
            self.state.dump()

    async def mqtt_ping_task(self, client: aiomqtt.Client) -> None:
        LOGGER.debug("MQTT Panel Client - Ping task started")
        while True:
            try:
                if self.controller_state == ControllerState.CONNECTED:
                    await self.commands.panel.pingevent()
                await asyncio.sleep(self.settings.mqtt_ping)

            except asyncio.CancelledError:
                raise

            except Exception as err:
                LOGGER.exception("MQTT Panel Client - error in ping task: %s", err)
                raise

    async def mqtt_zwave_meter_update(self) -> None:
        LOGGER.debug("MQTT Panel Client - Z-Wave meter update task started")
        while True:
            if self.controller_state == ControllerState.CONNECTED:
                for autdev in self.state.automation_devices:
                    if not isinstance(autdev, QolsysAutomationDeviceZwave):
                        continue

                    if not autdev._FIX_MULTICHANNEL_METER_ENDPOINT:
                        continue

                    for service in autdev.service_get_protocol(MeterServiceZwave):
                        if isinstance(service, MeterServiceZwave):
                            await service.refresh_meter_zwave()
                            await asyncio.sleep(5)

            await asyncio.sleep(300)

    def _to_event_dict(self) -> dict[str, Any]:
        return {
            "connected": self.controller_state == ControllerState.CONNECTED,
            "panel_ip": self.settings.panel_ip,
            "unique_id": self.panel.unique_id,
            "plugin_ip": self.settings.plugin_ip,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    def notify_panel_status_update(self) -> None:
        self.state.notify(Event(QolsysNotification.PANEL_STATUS_UPDATE, self.panel, self._to_event_dict()))

    async def start_initial_pairing(self) -> None:
        self._pairing_was_started = True
        # check if random_mac has been configured
        if self.settings.random_mac == "":
            # If pairing_resume is enabled, look for existing PKI folders to resume pairing process with previous random_mac
            resume_pki_id = await self._pki.pairing_resume_get_in_progress_pki()
            if self.settings.pairing_resume and resume_pki_id:
                self.settings.random_mac = resume_pki_id

            else:
                LOGGER.debug("Creating random_mac")
                self.settings.random_mac = generate_random_mac()
                await self._pki.create(self.settings.random_mac, key_size=self.settings.key_size)
                await self._pki.pairing_resume_pki_set(True)

        # Check if PKI is valid
        self._pki.set_id(self.settings.random_mac)
        LOGGER.debug("Checking PKI")
        if not (await self._pki.check_key_file() and await self._pki.check_cer_file() and await self._pki.check_csr_file()):
            raise QolsysConfigError("PKI files not found or invalid")

        LOGGER.debug("Starting Pairing Process")

        if not self.settings.check_plugin_ip():
            raise QolsysConfigError("Plugin IP Address not configured")

        # If we don't already have client signed certificate, start the pairing server
        if (
            not await self._pki.check_secure_file()
            or not await self._pki.check_qolsys_cer_file()
            or not self.settings.check_panel_ip()
        ):
            self._pairing_server = QolsysPairingServer(self.settings, self._pki)
            await self._pairing_server.start()
            await self._pairing_server.wait_until_paired()
            await self._pairing_server.stop()
            self._pairing_server = None

        LOGGER.debug("Sending MQTT Pairing Request to Panel")

        # We have client signed certificate at this point
        # Connect to Panel MQTT to send pairing command

    @property
    def controller_state(self) -> ControllerState:
        return self._controller_state

    async def set_controller_state(self, new_state: ControllerState) -> None:
        async with self._controller_state_condition:
            if new_state == self._controller_state:
                return

            if new_state not in VALID_CONTROLLER_TRANSITIONS[self._controller_state]:
                raise InvalidControllerStateTransitionError(f"{self._controller_state.name} -> {new_state.name}")

            LOGGER.debug("Controller State - %s -> %s", self._controller_state.name, new_state.name)

            self._controller_state = new_state
            self._controller_state_condition.notify_all()

        # Audit M2: notify observers here, after the new state is committed, so
        # that an entity reading controller_state during the callback sees the
        # state it is being told about. It used to be notified from the callers,
        # one of them before the flip, and entities went unavailable on
        # RECONNECTING only because a deferred state write happened to land
        # after it.
        self.notify_panel_status_update()

    async def wait_until_connected(self) -> None:
        async with self._controller_state_condition:
            await self._controller_state_condition.wait_for(lambda: self._controller_state == ControllerState.CONNECTED)
