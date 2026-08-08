"""The Qolsys Panel integration."""

from __future__ import annotations

import asyncio
import logging
import ssl

from qolsys_controller import qolsys_controller
from qolsys_controller.enum_qolsys import ControllerState, QolsysNotification
from qolsys_controller.errors import QolsysMqttError, QolsysSslError

from homeassistant.const import CONF_HOST, CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_RANDOM_MAC,
    DEFAULT_ARM_CODE_REQUIRED,
    DEFAULT_DISARM_CODE_REQUIRED,
    DEFAULT_MOTION_SENSOR_DELAY,
    DEFAULT_MOTION_SENSOR_DELAY_ENABLED,
    DOMAIN,
    OPTION_ARM_CODE,
    OPTION_DISARM_CODE,
    OPTION_MOTION_SENSOR_DELAY,
    OPTION_MOTION_SENSOR_DELAY_ENABLED,
)
from .services import async_setup_services
from .types import QolsysPanelConfigEntry
from .utils import get_local_ip

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.LOCK,
    Platform.MEDIA_PLAYER,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.SCENE,
    Platform.WEATHER,
    Platform.VALVE,
    Platform.SIREN,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# How long to wait for the panel to connect during setup before retrying.
_CONNECT_TIMEOUT_SECONDS = 30


def _setup_error(exc: BaseException | None) -> ConfigEntryError:
    """Map a fatal controller startup failure to the right ConfigEntry* error."""
    if isinstance(exc, (QolsysSslError, ssl.SSLError)):
        return ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="authentication_failed"
        )
    if isinstance(exc, QolsysMqttError):
        return ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="mqtt_error"
        )
    # QolsysConfigError or anything unexpected.
    return ConfigEntryNotReady(
        translation_domain=DOMAIN, translation_key="configuration_error"
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Qolsys Panel services."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: QolsysPanelConfigEntry) -> bool:
    """Set up Qolsys Panel from a config entry."""
    QolsysPanel = qolsys_controller()
    QolsysPanel.settings.config_directory = hass.config.config_dir + "/qolsys_panel/"
    QolsysPanel.settings.plugin_ip = await get_local_ip(hass=hass)
    QolsysPanel.settings.panel_ip = entry.data[CONF_HOST]
    QolsysPanel.settings.panel_mac = entry.data[CONF_MAC]
    QolsysPanel.settings.random_mac = entry.data[CONF_RANDOM_MAC]
    QolsysPanel.settings.log_mqtt_messages = False
    QolsysPanel.settings.auto_discover_pki = False
    QolsysPanel.settings.pairing_resume = False
    QolsysPanel.settings.mqtt_bridge_enabled = False

    arm_code_required = entry.options.get(OPTION_ARM_CODE, DEFAULT_ARM_CODE_REQUIRED)
    disarm_code_required = entry.options.get(
        OPTION_DISARM_CODE, DEFAULT_DISARM_CODE_REQUIRED
    )

    QolsysPanel.settings.check_user_code_on_arm = arm_code_required
    QolsysPanel.settings.check_user_code_on_disarm = disarm_code_required

    QolsysPanel.settings.motion_sensor_delay_sec = entry.options.get(
        OPTION_MOTION_SENSOR_DELAY, DEFAULT_MOTION_SENSOR_DELAY
    )
    QolsysPanel.settings.motion_sensor_delay = entry.options.get(
        OPTION_MOTION_SENSOR_DELAY_ENABLED, DEFAULT_MOTION_SENSOR_DELAY_ENABLED
    )

    # Start the controller (long-lived) and, separately, wait for the CONNECTED state.
    controller_task = hass.async_create_background_task(
        QolsysPanel.run_forever(reconnect=True, run_once=False, start_pairing=False),
        "qolsys-controller",
    )
    connected_task = hass.async_create_task(QolsysPanel.wait_until_connected())

    done, _pending = await asyncio.wait(
        {controller_task, connected_task},
        timeout=_CONNECT_TIMEOUT_SECONDS,
        return_when=asyncio.FIRST_COMPLETED,
    )

    if connected_task not in done or connected_task.exception() is not None:
        # Fatal startup failure or timeout: tear everything down and surface the reason.
        connected_task.cancel()
        await QolsysPanel.stop()
        controller_task.cancel()
        if controller_task in done:
            exc = controller_task.exception()
            _LOGGER.error("Qolsys Panel startup failed: %r", exc)
            raise _setup_error(exc) from exc
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="connection_timeout"
        )

    entry.runtime_data = QolsysPanel

    # Log once when the connection to the panel is lost and once when it is
    # restored.
    was_connected = True

    def _check_connection() -> None:
        nonlocal was_connected
        state = QolsysPanel.controller_state
        if was_connected and state == ControllerState.RECONNECTING:
            _LOGGER.info("Connection to Qolsys Panel lost, reconnecting")
        elif not was_connected and state == ControllerState.CONNECTED:
            _LOGGER.info("Connection to Qolsys Panel restored")
        was_connected = state == ControllerState.CONNECTED

    def _on_panel_status_update() -> None:
        hass.loop.call_soon(_check_connection)

    def _unregister_connection_logger() -> None:
        QolsysPanel.state.unregister(
            QolsysNotification.PANEL_STATUS_UPDATE, _on_panel_status_update
        )

    QolsysPanel.state.register(
        QolsysNotification.PANEL_STATUS_UPDATE, _on_panel_status_update
    )
    entry.async_on_unload(_unregister_connection_logger)

    device_registry = dr.async_get(hass)
    mac = entry.data.get(CONF_MAC)
    unique_id = entry.unique_id
    assert unique_id is not None

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
        identifiers={(DOMAIN, unique_id)},
        name="Panel",
        manufacturer="Johnson Controls",
        model=f"Qolsys Panel ({QolsysPanel.panel.HARDWARE_VERSION})",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: QolsysPanelConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        QolsysPanel = entry.runtime_data
        await QolsysPanel.stop()
    return unload_ok


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: QolsysPanelConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version < 1:
        # 0.x -> 1.0: the disarm code option was split out of the arm code
        # option; carry over the old combined behavior.
        new_options = {**config_entry.options}
        new_options.setdefault(
            OPTION_DISARM_CODE,
            new_options.get(OPTION_ARM_CODE, DEFAULT_ARM_CODE_REQUIRED),
        )
        hass.config_entries.async_update_entry(
            config_entry, options=new_options, minor_version=0, version=1
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True
