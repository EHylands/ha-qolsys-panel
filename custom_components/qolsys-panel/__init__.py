"""The Qolsys Panel integration."""

from __future__ import annotations

import logging

from qolsys_controller import qolsys_controller
from qolsys_controller.errors import QolsysSslError

from homeassistant.const import CONF_HOST, CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.typing import ConfigType

from .const import CONF_RANDOM_MAC, DOMAIN
from .types import QolsysPanelConfigEntry
from .utils import get_local_ip

logging.basicConfig(level=logging.DEBUG,format='%(levelname)s - %(module)s: %(message)s')
LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.LOCK,
    Platform.CLIMATE,
]

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Qolsys Panel services."""
    return True

# Update entry annotation
async def async_setup_entry(hass: HomeAssistant, entry: QolsysPanelConfigEntry) -> bool:
    """Set up Qolsys Panel from a config entry."""

    QolsysPanel = qolsys_controller(config_directory= f"{hass.config.config_dir}/qolsys_panel_hass/")
    QolsysPanel.select_plugin("remote")
    QolsysPanel.plugin.settings.plugin_ip = await get_local_ip(hass=hass)
    QolsysPanel.plugin.settings.panel_ip = entry.data[CONF_HOST]
    QolsysPanel.plugin.settings.panel_mac = entry.data[CONF_MAC]
    QolsysPanel.plugin.settings.random_mac = entry.data[CONF_RANDOM_MAC]

    # Additionnal remote plugin config
    QolsysPanel.plugin.check_user_code_on_disarm = False
    QolsysPanel.plugin.log_mqtt_mesages = False
    QolsysPanel.plugin.auto_discover_pki = False

    # Configure remote plugin
    if not await QolsysPanel.plugin.config(start_pairing=False):
        LOGGER.debug('Error Configuring remote plugin')
        return False

    # Start the plugin
    try:
        await QolsysPanel.plugin.start_operation()

    except QolsysSslError as err:
        LOGGER.error('Credentials rejected by panel')
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="authentication_failed"
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

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True

# Update entry annotation
async def async_unload_entry(
    hass: HomeAssistant, entry: QolsysPanelConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
