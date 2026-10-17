import asyncio
import logging
from typing import TYPE_CHECKING, Any

LOGGER = logging.getLogger(__name__)
logging.getLogger("transitions.core").setLevel(logging.ERROR)
logging.getLogger("amqtt").setLevel(logging.ERROR)
logging.getLogger("amqtt.core").setLevel(logging.ERROR)
logging.getLogger("amqtt.broker").setLevel(logging.ERROR)
logging.getLogger("amqtt.plugins").setLevel(logging.ERROR)

if TYPE_CHECKING:
    from ..controller import QolsysController
    from ..mqtt_bridge.bridge import MqttBridge


class MqttBridgeBroker:
    def __init__(self, bridge: "MqttBridge") -> None:
        self._bridge: MqttBridge = bridge
        self._controller: QolsysController = bridge._controller
        self._config: dict[str, Any] = {}
        self._broker: Any = None
        self._is_running: bool = False

    def _import_amqtt(self) -> tuple[Any, Any, Any, Any]:
        from amqtt.broker import Broker
        from amqtt.contexts import BaseContext
        from amqtt.plugins.authentication import BaseAuthPlugin
        from amqtt.session import Session

        return Broker, BaseContext, BaseAuthPlugin, Session

    def load_auth_plugin(self, enabled: bool) -> Any | None:
        if not enabled:
            return None
        from .auth_plugin import AuthPlugin

        return AuthPlugin

    async def run_bridge_broker(self, startup_event: asyncio.Event, startup_result: dict[str, bool | Exception]) -> None:
        try:
            LOGGER.info("MQTT Bridge Broker - Starting")
            if self._is_running:
                LOGGER.warning("MQTT Bridge Broker - Already running")
                startup_result["started"] = True
                startup_event.set()
                return
            self._is_running = True

            if self._controller.settings.mqtt_bridge_tls_enabled:
                await self._check_or_create_certificates()
            self._config = self._build_config()
            if not self._broker:
                self._broker = self._create_broker()
            if self._broker is None:
                startup_result["started"] = False
                startup_event.set()
                return
            self._broker.on_client_connected = self._on_client_connected
            self._broker.on_packet_received = self._on_packet_received
            await self._broker.start()

            LOGGER.info(
                "MQTT Bridge Broker - Listening on %s:%s",
                self._controller.settings.plugin_ip,
                self._controller.settings.mqtt_bridge_port,
            )
            LOGGER.info("MQTT Bridge Broker - Running")

            self._is_running = True
            startup_result["started"] = True
            startup_event.set()

            await asyncio.Future()  # Run until cancelled

        except asyncio.CancelledError:
            LOGGER.info("MQTT Bridge Broker - Shutting down ...")
            raise

        except Exception as err:
            self._is_running = False
            startup_result["error"] = err
            startup_event.set()
            LOGGER.error("MQTT Bridge Broker - Runtime error: %s", err)
            raise

        finally:
            self._is_running = False

            if not startup_event.is_set():
                startup_result["started"] = False
                startup_event.set()

            if self._broker is not None:
                loop = asyncio.get_event_loop()
                original_handler = loop.get_exception_handler()

                def _shutdown_exc_handler(loop: Any, context: Any) -> None:
                    exc = context.get("exception")
                    # amqtt writes to already-closed sockets after cancellation; suppress silently
                    if isinstance(exc, OSError) and exc.errno == 9:
                        return
                    if original_handler is not None:
                        original_handler(loop, context)
                    else:
                        loop.default_exception_handler(context)

                loop.set_exception_handler(_shutdown_exc_handler)
                try:
                    await asyncio.wait_for(
                        self._broker.shutdown(),
                        timeout=5,
                    )
                    LOGGER.info("MQTT Bridge Broker - Shutdown completed")

                except asyncio.TimeoutError:
                    LOGGER.warning("MQTT Bridge Broker - Shutdown timed out")

                except Exception as err:
                    LOGGER.debug("MQTT Bridge Broker - Error during shutdown: %s", err)

                finally:
                    loop.set_exception_handler(original_handler)

    async def _on_client_connected(self, client_id: str) -> None:
        LOGGER.info("MQTT Bridge Broker - Client connected: %s", client_id)

    async def _on_packet_received(self, client_id: str, topic: str, payload: bytes) -> None:
        LOGGER.debug("MQTT Bridge Broker - Packet received from client %s on topic %s: %s", client_id, topic, payload)

    async def wait_for_broker_start(self, timeout: int = 5) -> None:
        start_time = asyncio.get_event_loop().time()
        while self._broker.transitions.state != "started":
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError("MQTT Bridge Broker did not start in time")
            await asyncio.sleep(0.05)
        LOGGER.info("MQTT Bridge Broker - Running")

    async def _check_or_create_certificates(self) -> None:
        if (
            not await self._controller._pki.check_mqtt_bridge_key_file()
            or not await self._controller._pki.check_mqtt_bridge_cer_file()
        ):
            LOGGER.debug("MQTT Bridge Broker - Certificates not found, creating new certificates")
            await self._controller._pki.create_mqtt_bridge_certificates()

    def _create_broker(self) -> Any:
        Broker, _, _, _ = self._import_amqtt()
        broker = Broker(self._config)
        return broker

    def _build_config(self) -> dict[str, Any]:
        listener: dict[str, Any] = {
            "type": "tcp",
            "bind": f"{self._controller.settings.plugin_ip}:{self._controller.settings.mqtt_bridge_port}",
            "ssl": self._controller.settings.mqtt_bridge_tls_enabled,
            "max_connections": self._controller.settings.mqtt_bridge_max_connections,
        }

        if self._controller.settings.mqtt_bridge_tls_enabled:
            listener["certfile"] = str(self._controller._pki.mqtt_bridge_cer_file_path)
            listener["keyfile"] = str(self._controller._pki.mqtt_bridge_key_file_path)

        listeners = {"default": listener}

        # Plugin selection
        plugins: dict[str, dict[str, Any]] = {}
        # Vendored: the amqtt plugin loader resolves this by dotted path, which moved
        # when the library was vendored into the integration.
        plugins[f"{__package__}.auth_plugin.AuthPlugin"] = {
            "allowed_users": self._controller.settings.mqtt_bridge_broker_allowed_users
        }

        return {"listeners": listeners, "plugins": plugins}
