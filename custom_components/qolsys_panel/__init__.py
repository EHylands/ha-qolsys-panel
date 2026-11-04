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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
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
    Platform.EVENT,
    Platform.SCENE,
    Platform.WEATHER,
    Platform.VALVE,
    Platform.SIREN,
    Platform.IMAGE,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# How long to wait for the panel to connect during setup before retrying.
_CONNECT_TIMEOUT_SECONDS = 30


def _setup_error(
    exc: BaseException | None,
) -> ConfigEntryAuthFailed | ConfigEntryNotReady:
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

    # Prune devices the panel no longer reports (e.g. a zone deleted on the
    # panel) so they don't linger across reloads.
    _async_remove_stale_devices(hass, entry, QolsysPanel)

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


def _panel_object_present(QolsysPanel: qolsys_controller, suffix: str) -> bool:
    """Return True if the device identified by `suffix` still exists on the panel.

    `suffix` is the part of a child device identifier after ``"{unique_id}_"``
    (see `entity.py`), e.g. ``"zone5"``, ``"partition0"``, ``"autdev_12"`` or
    ``"camera3"``. Unknown suffixes are treated as absent so the device can be
    cleaned up.
    """
    state = QolsysPanel.state
    if suffix.startswith("partition"):
        return state.partition(suffix[len("partition") :]) is not None
    if suffix.startswith("zone"):
        return state.zone(suffix[len("zone") :]) is not None
    if suffix.startswith("autdev_"):
        return state.automation_device(suffix[len("autdev_") :]) is not None
    if suffix.startswith("camera"):
        return state.ip_camera(suffix[len("camera") :]) is not None
    return False


def _device_removable(
    QolsysPanel: qolsys_controller, unique_id: str, device_entry: dr.DeviceEntry
) -> bool:
    """Return True if `device_entry` no longer maps to a device on the panel.

    The root panel device and any zone, partition, automation device or camera
    the panel still reports are kept; stale or unknown devices are removable.
    """
    prefix = f"{unique_id}_"
    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue
        # The panel itself is the integration's root device; it is removed by
        # deleting the integration, not individual devices.
        if identifier == unique_id:
            return False
        if identifier.startswith(prefix) and _panel_object_present(
            QolsysPanel, identifier[len(prefix) :]
        ):
            return False

    return True


def _async_remove_stale_devices(
    hass: HomeAssistant,
    entry: QolsysPanelConfigEntry,
    QolsysPanel: qolsys_controller,
) -> None:
    """Remove registry devices the panel no longer reports.

    Runs on every setup/reload so a zone, automation device or camera deleted
    on the panel doesn't linger in Home Assistant. The manual per-device delete
    (`async_remove_config_entry_device`) remains available as a fallback.
    """
    unique_id = entry.unique_id
    if unique_id is None:
        return

    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if _device_removable(QolsysPanel, unique_id, device):
            _LOGGER.info(
                "Removing stale device %s (%s); no longer present on the panel",
                device.name_by_user or device.name,
                device.id,
            )
            device_registry.async_remove_device(device.id)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow deleting a device only when it no longer exists on the panel.

    Returning True lets the user remove the (stale) device from Home Assistant;
    returning False keeps it because it is the panel device or still
    corresponds to a zone, partition, automation device or camera the panel
    currently reports.
    """
    unique_id = config_entry.unique_id
    QolsysPanel = getattr(config_entry, "runtime_data", None)

    # Without the loaded controller or a unique id we can't inspect panel
    # state, so don't stand in the way of removal.
    if unique_id is None or QolsysPanel is None:
        return True

    name = device_entry.name_by_user or device_entry.name
    if _device_removable(QolsysPanel, unique_id, device_entry):
        _LOGGER.info(
            "Removing device %s (%s); it is no longer present on the panel",
            name,
            device_entry.id,
        )
        return True

    _LOGGER.debug(
        "Refusing to delete device %s (%s); it is the panel device or still "
        "present on the panel",
        name,
        device_entry.id,
    )
    return False


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
