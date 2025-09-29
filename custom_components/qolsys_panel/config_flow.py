"""Config flow for Qolsys Panel integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from qolsys_controller import qolsys_controller
from qolsys_controller.errors import QolsysSslError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import selector

from .const import CONF_IMEI, CONF_PANEL_IP, CONF_RANDOM_MAC, DOMAIN
from .utils import get_local_ip

_LOGGER = logging.getLogger(__name__)

class QolsysPanelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qolsys Panel."""

    VERSION = 0
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Init config flow."""

        self._data: dict[str, Any] = {}
        self._pki_list = []
        self._config_directory = ""
        self._QolsysPanel = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        self._QolsysPanel = qolsys_controller()
        self._QolsysPanel.select_plugin("remote")
        self._QolsysPanel.plugin.settings.config_directory = self.hass.config.config_dir + "/qolsys_panel_hass/"
        self._QolsysPanel.plugin.log_mqtt_mesages = False

        return self.async_show_menu(
            step_id="user",
            menu_options={
                "pki_autodiscovery_1": "Automatic PKI Discovery and Pairing",
                "existing_pki": "Use Existing PKI",
            },
        )

    async def async_step_pki_autodiscovery_1(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle thepki_autodiscovery step - User message."""
        _LOGGER.debug("pki_autodiscovery_1: User information")

        if user_input is None:
            return self.async_show_form(
                step_id="pki_autodiscovery_1",
            )

        return await self.async_step_pki_autodiscovery_2()

    async def async_step_pki_autodiscovery_2(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the pki_autodiscovery step 2 - Load Plugin."""
        _LOGGER.debug("pki_autodiscovery_2: Loading plugin")

        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="pki_autodiscovery_2",
            )

        self._QolsysPanel.plugin.settings.plugin_ip = await get_local_ip(hass=self.hass)
        self._QolsysPanel.plugin.settings.panel_ip = ""
        self._QolsysPanel.plugin.settings.random_mac = ""
        self._QolsysPanel.plugin.auto_discover_pki = True

        if not await self.async_validate_pki():
            errors["base"] = "Error pairing and connecting to panel"
            return self.async_show_form(
                step_id="pki_autodiscovery_2",
                data_schema=None,
                errors=errors,
            )

        # Add entry to Home Assistant
        await self.async_set_unique_id(format_mac(self._QolsysPanel.panel.MAC_ADDRESS))
        self._abort_if_unique_id_configured()

        self._data[CONF_MAC] = format_mac(self._QolsysPanel.panel.MAC_ADDRESS)
        self._data[CONF_HOST] = self._QolsysPanel.settings.panel_ip
        self._data[CONF_MODEL] = self._QolsysPanel.panel.product_type
        self._data[CONF_RANDOM_MAC] = format_mac(self._QolsysPanel.settings.random_mac)
        self._data[CONF_IMEI] = self._QolsysPanel.panel.imei

        return self.async_create_entry(
            title=f"Qolsys Panel ({self._data[CONF_MAC]})",
            data=self._data,
        )

    async def async_step_existing_pki(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the existing_pki step."""

        errors: dict[str, str] = {}

        self._pki_list = []
        path = Path(self._config_directory + "pki/")
        directories = [p.name for p in path.iterdir() if p.is_dir()]
        for d in directories:
            self._pki_list.append(":".join(d[i : i + 2] for i in range(0, len(d), 2)))

        data_schema = {
            vol.Required(CONF_PANEL_IP): str,
            vol.Required(CONF_RANDOM_MAC): selector(
                {
                    "select": {
                        "options": self._pki_list,
                        "multiple": False,
                        "mode": "dropdown",
                    }
                }
            ),
        }

        # Abord if no PKI available
        if not self._pki_list:
            errors["base"] = "No existing PKI found in configuration folder"
            return self.async_show_form(
                step_id="existing_pki",
                data_schema=vol.Schema(data_schema),
                errors=errors,
            )

        if user_input is None:
            return self.async_show_form(
                step_id="existing_pki", data_schema=vol.Schema(data_schema)
            )

        self._QolsysPanel.plugin.settings.plugin_ip = await get_local_ip(hass=self.hass)
        self._QolsysPanel.plugin.settings.panel_ip = user_input[CONF_PANEL_IP]
        self._QolsysPanel.plugin.settings.random_mac = user_input[CONF_RANDOM_MAC]
        self._QolsysPanel.plugin.auto_discover_pki = False

        # Check if PKI is valid
        self._QolsysPanel.plugin._pki.set_id(user_input[CONF_RANDOM_MAC])
        if (
            not self._QolsysPanel.plugin._pki.check_key_file()
            or not self._QolsysPanel.plugin._pki.check_cer_file()
            or not self._QolsysPanel.plugin._pki.check_csr_file()
        ):  # noqa: SLF001
            errors["base"] = f"Invalid PKI: {user_input[CONF_RANDOM_MAC]}"
            return self.async_show_form(
                step_id="existing_pki",
                data_schema=vol.Schema(data_schema),
                errors=errors,
            )

        if not self._QolsysPanel.settings.check_panel_ip():
            errors["base"] = f"Invalid Panel IP: {self._QolsysPanel.settings.panel_ip}"
            return self.async_show_form(
                step_id="existing_pki",
                data_schema=vol.Schema(data_schema),
                errors=errors,
            )

        if not self._QolsysPanel.settings.check_plugin_ip():
            errors["base"] = (
                f"Invalid Plugin IP: {self._QolsysPanel.settings.plugin_ip}"
            )
            return self.async_show_form(
                step_id="existing_pki",
                data_schema=vol.Schema(data_schema),
                errors=errors,
            )

        if not await self.async_validate_pki():
            errors["base"] = "Error pairing and connecting to panel"
            return self.async_show_form(
                step_id="existing_pki",
                data_schema=vol.Schema(data_schema),
                errors=errors,
            )

        # Add entry to Home Assistant
        await self.async_set_unique_id(format_mac(self._QolsysPanel.panel.MAC_ADDRESS))
        self._abort_if_unique_id_configured()

        self._data[CONF_MAC] = format_mac(self._QolsysPanel.panel.MAC_ADDRESS)
        self._data[CONF_HOST] = self._QolsysPanel.settings.panel_ip
        self._data[CONF_MODEL] = self._QolsysPanel.panel.product_type
        self._data[CONF_RANDOM_MAC] = format_mac(self._QolsysPanel.settings.random_mac)
        self._data[CONF_IMEI] = self._QolsysPanel.panel.imei

        return self.async_create_entry(
            title=f"Qolsys Panel ({self._data[CONF_MAC]})",
            data=self._data,
        )

    async def async_validate_pki(self) -> bool:
        """Validate the user input allows us to connect."""
        if not await self._QolsysPanel.plugin.config(start_pairing=True):
            _LOGGER.debug("Error configuring plugin")
            return False

        try:
            await self._QolsysPanel.plugin.mqtt_connect_task(reconnect=False)
        except QolsysSslError:
            _LOGGER.debug("credential error Error connecting to panel")
            return False

        _LOGGER.debug("Plugin is configured")

        return True
