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
    CONF_MOTION_SENSOR_DELAY_ENABLED,
    CONF_MOTION_SENSOR_DELAY,
    DOMAIN
)

from .types import QolsysPanelConfigEntry
from .utils import get_local_ip

logging.basicConfig(level=logging.DEBUG,format='%(levelname)s - %(module)s: %(message)s')
LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.LOCK,
    Platform.CLIMATE,
    Platform.SCENE
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Qolsys Panel services."""
    return True

# Update entry annotation
async def async_setup_entry(hass: HomeAssistant, entry: QolsysPanelConfigEntry) -> bool:
    """Set up Qolsys Panel from a config entry."""

    QolsysPanel = qolsys_controller()
    QolsysPanel.select_plugin("remote")
    QolsysPanel.plugin.settings.config_directory = hass.config.config_dir + "/qolsys_panel/"
    QolsysPanel.plugin.settings.plugin_ip = await get_local_ip(hass=hass)
    QolsysPanel.plugin.settings.mqtt_timeout = 30
    QolsysPanel.plugin.settings.mqtt_ping = 600
    QolsysPanel.plugin.settings.motion_sensor_delay = entry.data[CONF_MOTION_SENSOR_DELAY_ENABLED]
    QolsysPanel.plugin.settings.panel_ip = entry.data[CONF_HOST]
    QolsysPanel.plugin.settings.panel_mac = entry.data[CONF_MAC]
    QolsysPanel.plugin.settings.random_mac = entry.data[CONF_RANDOM_MAC]

    # Additionnal remote plugin config
    QolsysPanel.plugin.check_user_code_on_disarm = False
    QolsysPanel.plugin.check_user_code_on_arm = False
    QolsysPanel.plugin.log_mqtt_mesages = False
    QolsysPanel.plugin.auto_discover_pki = False

    # Configure remote plugin
    if not await QolsysPanel.plugin.config(start_pairing=False):
        LOGGER.error('Error Configuring remote plugin')
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_configure",
        )

    # Start plugin operation
    try:
        await QolsysPanel.plugin.start_operation()

    except QolsysSslError as err:
        LOGGER.error('Credentials rejected by panel - Signed Certificate Error')
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="authentication_failed"
        ) from err
    
    except QolsysMqttError as err:
        LOGGER.error('MQTT Error')
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="mqtt_error"
        ) from err

    if not QolsysPanel.plugin.connected:
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
        model=f'Qolsys Panel ({QolsysPanel.panel.HARDWARE_VERSION})',
        sw_version=QolsysPanel.panel.ANDROID_VERSION,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

# Update entry annotation
async def async_unload_entry(
    hass: HomeAssistant, entry: QolsysPanelConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.plugin.stop_operation()
    return unload_ok

async def async_migrate_entry(hass, config_entry: QolsysPanelConfigEntry):
    """Migrate old entry."""
    LOGGER.debug("Migrating configuration from version %s.%s", config_entry.version, config_entry.minor_version)

    if config_entry.version > 0:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 0:
        new_data = {**config_entry.data}
        if config_entry.minor_version < 4:
            if CONF_MOTION_SENSOR_DELAY_ENABLED not in new_data:
                new_data[CONF_MOTION_SENSOR_DELAY_ENABLED] = True

            if CONF_MOTION_SENSOR_DELAY not in new_data:
                new_data[CONF_MOTION_SENSOR_DELAY] = 6

    hass.config_entries.async_update_entry(config_entry, data=new_data, minor_version=2, version=0)

    LOGGER.debug("Migration to configuration version %s.%s successful", config_entry.version, config_entry.minor_version)
    return True