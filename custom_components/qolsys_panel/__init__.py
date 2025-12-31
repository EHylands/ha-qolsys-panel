"""The Qolsys Panel integration."""

from __future__ import annotations

import logging

from qolsys_controller import qolsys_controller
from qolsys_controller.errors import QolsysSslError, QolsysMqttError

from homeassistant.const import CONF_HOST, CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import config_validation as cv


from .const import (
    CONF_RANDOM_MAC,
    DOMAIN,
    DEFAULT_ARM_CODE_REQUIRED,
    DEFAULT_MOTION_SENSOR_DELAY_ENABLED,
    DEFAULT_MOTION_SENSOR_DELAY,
    OPTION_ARM_CODE,
    OPTION_MOTION_SENSOR_DELAY_ENABLED,
    OPTION_MOTION_SENSOR_DELAY,
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
    Platform.CLIMATE,
    Platform.COVER,
    Platform.SCENE,
    Platform.WEATHER,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


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
    QolsysPanel.settings.log_mqtt_mesages = False
    QolsysPanel.settings.auto_discover_pki = False

    user_code_required = entry.options.get(OPTION_ARM_CODE, DEFAULT_ARM_CODE_REQUIRED)
    QolsysPanel.settings.check_user_code_on_arm = user_code_required
    QolsysPanel.settings.check_user_code_on_disarm = user_code_required

    QolsysPanel.settings.motion_sensor_delay_sec = entry.options.get(
        OPTION_MOTION_SENSOR_DELAY, DEFAULT_MOTION_SENSOR_DELAY
    )
    QolsysPanel.settings.motion_sensor_delay = entry.options.get(
        OPTION_MOTION_SENSOR_DELAY_ENABLED, DEFAULT_MOTION_SENSOR_DELAY_ENABLED
    )

    # Configure controller
    if not await QolsysPanel.config(start_pairing=False):
        _LOGGER.error("Error Configuring Controller")
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_configure",
        )

    # Start controller operation
    try:
        await QolsysPanel.start_operation()

    except QolsysSslError as err:
        _LOGGER.error("Credentials rejected by panel - Signed Certificate Error")
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="authentication_failed"
        ) from err

    except QolsysMqttError as err:
        _LOGGER.error("MQTT Error")
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="mqtt_error"
        ) from err

    if not QolsysPanel.connected:
        _LOGGER.error("Unable to connect to panel")
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        )

    entry.runtime_data = QolsysPanel
    device_registry = dr.async_get(hass)
    mac = entry.data.get(CONF_MAC)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
        identifiers={(DOMAIN, entry.unique_id)},
        name="Panel",
        manufacturer="Johnson Controls",
        model=f"Qolsys Panel ({QolsysPanel.panel.HARDWARE_VERSION})",
        sw_version=QolsysPanel.panel.ANDROID_VERSION,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: QolsysPanelConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.stop_operation()
    return unload_ok


async def async_migrate_entry(hass, config_entry: QolsysPanelConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 0:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 0:
        new_data = {**config_entry.data}
        if config_entry.minor_version < 4:
            pass

    hass.config_entries.async_update_entry(
        config_entry, data=new_data, minor_version=3, version=0
    )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True
