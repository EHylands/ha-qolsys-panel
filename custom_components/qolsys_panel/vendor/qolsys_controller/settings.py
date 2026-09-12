from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from zeroconf.asyncio import AsyncZeroconf

from .errors import QolsysConfigError
from .file_permissions import SECRET_DIR_MODE, set_mode

LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .controller import QolsysController


class QolsysSettings:
    def __init__(self, controller: QolsysController) -> None:
        self._controller = controller

        # Plugin
        self._plugin_ip: str = ""
        self._random_mac: str = ""
        self._panel_mac: str = ""
        self._panel_ip: str = ""
        self._shared_zeroconf_instance: AsyncZeroconf | None = None

        # Path
        self._config_directory: Path = Path()
        self._pki_directory: Path = Path()
        self._media_directory: Path = Path()
        self._mqtt_bridge_directory: Path = Path()
        self._users_file_path: Path = Path()

        # Pki
        self._key_size: int = 2048
        self._auto_discover_pki: bool = False
        self._pairing_resume: bool = False
        self._pairing_progress_file: str = "pairing_progress.txt"

        # Pairing Server
        self._pairing_timeout: int = 180  # seconds (3 minutes)
        self._pairing_port: int = 0  # 0 = pick a random high port on start

        # MQTT Panel CLIENT - Used to connect to main IQ Panel
        self._mqtt_timeout: int = 30
        self._mqtt_ping: int = 300
        self._mqtt_qos: int = 0
        self._mqtt_remote_client_id: str = ""
        self._log_mqtt_messages: bool = False
        self._mqtt_command_timeout: int = 30

        # MQTT BRIDGE
        # Audit M8: the bridge carries a second disarm path; default it off so a
        # caller has to ask for it.
        self._mqtt_bridge_enabled: bool = False
        self._mqtt_bridge_port: int = 1883
        self._mqtt_bridge_hostname: str = ""
        self._mqtt_bridge_tls_enabled: bool = True
        self._mqtt_bridge_folder = "mqtt_bridge"

        # MQTT BRIDGE CLIENT
        self._mqtt_bridge_root_topic: str = "qolsys"
        self._mqtt_bridge_friendly_name: str = "iq_panel"
        self._mqtt_bridge_client_id = "qolsys_controller_mqtt_bridge_client"
        self._mqtt_bridge_client_username: str = ""
        self._mqtt_bridge_client_password: str = ""

        # MQTT BRIDGE BROKER
        self._mqtt_bridge_broker_enabled: bool = False
        self._mqtt_bridge_broker_allowed_users: dict[str, str] = {}
        self._mqtt_bridge_max_connections: int = 5
        self._mqtt_bridge_cerfile: str = "mqtt_bridge.cer"
        self._mqtt_bridge_keyfile: str = "mqtt_bridge.key"

        # Operation
        self._motion_sensor_delay: bool = True
        self._motion_sensor_delay_sec: int = 310
        self._check_user_code_on_arm: bool = False
        self._check_user_code_on_disarm: bool = True

    def check_panel_ip(self) -> bool:
        if self._panel_ip == "":
            LOGGER.debug("Invalid Panel IP:  %s", self._panel_ip)
            return False

        LOGGER.debug("Found Panel IP: %s", self._panel_ip)
        return True

    def check_plugin_ip(self) -> bool:
        if self._plugin_ip == "":
            LOGGER.debug("Invalid Plugin IP:  %s", self._plugin_ip)
            return False

        LOGGER.debug("Found Plugin IP: %s", self._plugin_ip)
        return True

    # -----------------------------
    # properties + setters
    # -----------------------------

    @property
    def shared_zeroconf_instance(self) -> AsyncZeroconf | None:
        return self._shared_zeroconf_instance

    @shared_zeroconf_instance.setter
    def shared_zeroconf_instance(self, zeroconf: AsyncZeroconf) -> None:
        self._shared_zeroconf_instance = zeroconf

    @property
    def mqtt_bridge_enabled(self) -> bool:
        return self._mqtt_bridge_enabled

    @mqtt_bridge_enabled.setter
    def mqtt_bridge_enabled(self, value: bool) -> None:
        self._mqtt_bridge_enabled = value

    @property
    def mqtt_bridge_broker_enabled(self) -> bool:
        return self._mqtt_bridge_broker_enabled

    @mqtt_bridge_broker_enabled.setter
    def mqtt_bridge_broker_enabled(self, value: bool) -> None:
        self._mqtt_bridge_broker_enabled = value

    @property
    def mqtt_bridge_port(self) -> int:
        return self._mqtt_bridge_port

    @mqtt_bridge_port.setter
    def mqtt_bridge_port(self, port: int) -> None:
        self._mqtt_bridge_port = port

    @property
    def mqtt_bridge_hostname(self) -> str:
        return self._mqtt_bridge_hostname

    @mqtt_bridge_hostname.setter
    def mqtt_bridge_hostname(self, hostname: str) -> None:
        self._mqtt_bridge_hostname = hostname

    @property
    def mqtt_bridge_client_username(self) -> str:
        return self._mqtt_bridge_client_username

    @mqtt_bridge_client_username.setter
    def mqtt_bridge_client_username(self, username: str) -> None:
        self._mqtt_bridge_client_username = username

    @property
    def mqtt_bridge_client_password(self) -> str:
        return self._mqtt_bridge_client_password

    @mqtt_bridge_client_password.setter
    def mqtt_bridge_client_password(self, password: str) -> None:
        self._mqtt_bridge_client_password = password

    @property
    def mqtt_bridge_root_topic(self) -> str:
        return self._mqtt_bridge_root_topic

    @mqtt_bridge_root_topic.setter
    def mqtt_bridge_root_topic(self, root_topic: str) -> None:
        self._mqtt_bridge_root_topic = root_topic

    @property
    def mqtt_bridge_friendly_name(self) -> str:
        return self._mqtt_bridge_friendly_name

    @mqtt_bridge_friendly_name.setter
    def mqtt_bridge_friendly_name(self, friendly_name: str) -> None:
        self._mqtt_bridge_friendly_name = friendly_name

    @property
    def mqtt_bridge_max_connections(self) -> int:
        return self._mqtt_bridge_max_connections

    @mqtt_bridge_max_connections.setter
    def mqtt_bridge_max_connections(self, max_connections: int) -> None:
        self._mqtt_bridge_max_connections = max_connections

    @property
    def mqtt_bridge_broker_allowed_users(self) -> dict[str, str]:
        return self._mqtt_bridge_broker_allowed_users

    @mqtt_bridge_broker_allowed_users.setter
    def mqtt_bridge_broker_allowed_users(self, allowed_users: dict[str, str]) -> None:
        self._mqtt_bridge_broker_allowed_users = allowed_users

    @property
    def mqtt_bridge_tls_enabled(self) -> bool:
        return self._mqtt_bridge_tls_enabled

    @mqtt_bridge_tls_enabled.setter
    def mqtt_bridge_tls_enabled(self, value: bool) -> None:
        self._mqtt_bridge_tls_enabled = value

    @property
    def random_mac(self) -> str:
        return self._random_mac

    @random_mac.setter
    def random_mac(self, random_mac: str) -> None:
        self._random_mac = random_mac.lower()

    @property
    def plugin_ip(self) -> str:
        return self._plugin_ip

    @plugin_ip.setter
    def plugin_ip(self, plugin_ip: str) -> None:
        self._plugin_ip = plugin_ip

    @property
    def panel_mac(self) -> str:
        return self._panel_mac

    @panel_mac.setter
    def panel_mac(self, panel_mac: str) -> None:
        self._panel_mac = panel_mac

    @property
    def panel_ip(self) -> str:
        return self._panel_ip

    @panel_ip.setter
    def panel_ip(self, panel_ip: str) -> None:
        self._panel_ip = panel_ip

    @property
    def log_mqtt_messages(self) -> bool:
        return self._log_mqtt_messages

    @log_mqtt_messages.setter
    def log_mqtt_messages(self, log_mqtt_messages: bool) -> None:
        self._log_mqtt_messages = log_mqtt_messages

    @property
    def check_user_code_on_disarm(self) -> bool:
        return self._check_user_code_on_disarm

    @check_user_code_on_disarm.setter
    def check_user_code_on_disarm(self, check_user_code_on_disarm: bool) -> None:
        self._check_user_code_on_disarm = check_user_code_on_disarm

    @property
    def check_user_code_on_arm(self) -> bool:
        return self._check_user_code_on_arm

    @check_user_code_on_arm.setter
    def check_user_code_on_arm(self, check_user_code_on_arm: bool) -> None:
        self._check_user_code_on_arm = check_user_code_on_arm

    @property
    def auto_discover_pki(self) -> bool:
        return self._auto_discover_pki

    @auto_discover_pki.setter
    def auto_discover_pki(self, value: bool) -> None:
        self._auto_discover_pki = value

    @property
    def mqtt_timeout(self) -> int:
        return self._mqtt_timeout

    @mqtt_timeout.setter
    def mqtt_timeout(self, value: int) -> None:
        self._mqtt_timeout = value

    @property
    def mqtt_ping(self) -> int:
        return self._mqtt_ping

    @mqtt_ping.setter
    def mqtt_ping(self, value: int) -> None:
        self._mqtt_ping = value

    @property
    def motion_sensor_delay(self) -> bool:
        return self._motion_sensor_delay

    @motion_sensor_delay.setter
    def motion_sensor_delay(self, value: bool) -> None:
        self._motion_sensor_delay = value

    @property
    def motion_sensor_delay_sec(self) -> int:
        return self._motion_sensor_delay_sec

    @motion_sensor_delay_sec.setter
    def motion_sensor_delay_sec(self, value: int) -> None:
        self._motion_sensor_delay_sec = value

    @property
    def config_directory(self) -> Path:
        return self._config_directory

    @config_directory.setter
    def config_directory(self, config_directory: str) -> None:
        self._config_directory = Path(config_directory)
        self._pki_directory = self._config_directory.joinpath("pki")
        self._media_directory = self._config_directory.joinpath("media")
        self._users_file_path = self._config_directory.joinpath("users.conf")
        self._mqtt_bridge_directory = self._config_directory.joinpath(self._mqtt_bridge_folder)

    @property
    def pki_directory(self) -> Path:
        return self._pki_directory

    @property
    def users_file_path(self) -> Path:
        return self._users_file_path

    @property
    def mqtt_bridge_directory(self) -> Path:
        return self._mqtt_bridge_directory

    @property
    def key_size(self) -> int:
        return self._key_size

    @property
    def mqtt_qos(self) -> int:
        return self._mqtt_qos

    @property
    def mqtt_remote_client_id(self) -> str:
        return self._mqtt_remote_client_id

    @mqtt_remote_client_id.setter
    def mqtt_remote_client_id(self, client_id: str) -> None:
        self._mqtt_remote_client_id = client_id

    @property
    def pairing_resume(self) -> bool:
        return self._pairing_resume

    @pairing_resume.setter
    def pairing_resume(self, value: bool) -> None:
        self._pairing_resume = value

    @property
    def pairing_timeout(self) -> int:
        return self._pairing_timeout

    @pairing_timeout.setter
    def pairing_timeout(self, value: int) -> None:
        self._pairing_timeout = value

    @property
    def pairing_port(self) -> int:
        return self._pairing_port

    @pairing_port.setter
    def pairing_port(self, value: int) -> None:
        self._pairing_port = value

    @property
    def pairing_progress_file(self) -> str:
        return self._pairing_progress_file

    @pairing_progress_file.setter
    def pairing_progress_file(self, value: str) -> None:
        self._pairing_progress_file = value

    def check_config_directory(self, create: bool = True) -> None:
        if not self.config_directory.is_dir():
            if not create:
                raise QolsysConfigError(f"config_directory not found and create is set to False:  {self.config_directory}")

            # Create config directory if not found
            LOGGER.debug("Creating config_directory: %s", self.config_directory)
            try:
                self.config_directory.mkdir(parents=True)
            except PermissionError:
                raise QolsysConfigError(f"Permission denied: Unable to create: {self.config_directory}")

            except Exception:
                raise QolsysConfigError(f"Error creating config_directory: {self.config_directory}")

        LOGGER.debug("Using config_directory: %s", self.config_directory.resolve())

        # Create pki directory if not found
        if not self.pki_directory.is_dir():
            LOGGER.debug("Creating pki_directory: %s", self.pki_directory.resolve())
            try:
                self.pki_directory.mkdir(parents=True)
            except PermissionError:
                raise QolsysConfigError(f"Permission denied: Unable to create: {self.pki_directory.resolve()}")
            except Exception:
                raise QolsysConfigError(f"Error creating pki_directory: {self.pki_directory.resolve()}")

        # Audit H2: the PKI tree holds the keypad private key.
        set_mode(self.pki_directory, SECRET_DIR_MODE)

        LOGGER.debug("Using pki_directory: %s", self.pki_directory.resolve())

        # Create media directory if not found
        if not self._media_directory.is_dir():
            LOGGER.debug("Creating media_directory: %s", self._media_directory.resolve())
            try:
                self._media_directory.mkdir(parents=True)
            except PermissionError:
                raise QolsysConfigError(f"Permission denied: Unable to create: {self._media_directory.resolve()}")
            except Exception:
                raise QolsysConfigError(f"Error creating media_directory: {self._media_directory.resolve()}")

        LOGGER.debug("Using media_directory: %s", self._media_directory.resolve())

        # Create MQTT Bridge directory if not found
        if not self.mqtt_bridge_directory.is_dir():
            LOGGER.debug("Creating mqtt_bridge_directory: %s", self.mqtt_bridge_directory.resolve())
            try:
                self.mqtt_bridge_directory.mkdir(parents=True)
            except PermissionError:
                raise QolsysConfigError(f"Permission denied: Unable to create: {self.mqtt_bridge_directory.resolve()}")
            except Exception:
                raise QolsysConfigError(f"Error creating mqtt_bridge_directory: {self.mqtt_bridge_directory.resolve()}")

        set_mode(self.mqtt_bridge_directory, SECRET_DIR_MODE)

        LOGGER.debug("Using mqtt_bridge: %s", self.mqtt_bridge_directory.resolve())

        return
