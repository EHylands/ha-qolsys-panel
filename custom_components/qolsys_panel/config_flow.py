"""Config flow for Qolsys Panel integration."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from qolsys_controller import qolsys_controller
from qolsys_controller.errors import QolsysSslError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import selector
from homeassistant.core import callback
from homeassistant.data_entry_flow import section


from .types import QolsysPanelConfigEntry

from .const import (
    CONF_IMEI,
    CONF_RANDOM_MAC,
    DEFAULT_ARM_CODE_REQUIRED,
    DEFAULT_DISARM_CODE_REQUIRED,
    DEFAULT_TRIGGER_AUXILLIARY,
    DEFAULT_TRIGGER_FIRE,
    DEFAULT_TRIGGER_POLICE,
    DEFAULT_MOTION_SENSOR_DELAY,
    DEFAULT_MOTION_SENSOR_DELAY_ENABLED,
    DOMAIN,
    OPTION_ARM_CODE,
    OPTION_DISARM_CODE,
    OPTION_MOTION_SENSOR_DELAY,
    OPTION_MOTION_SENSOR_DELAY_ENABLED,
    OPTION_TRIGGER_POLICE,
    OPTION_TRIGGER_AUXILLIARY,
    OPTION_TRIGGER_FIRE,
)

from .utils import get_local_ip

_LOGGER = logging.getLogger(__name__)


class QolsysPanelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qolsys Panel."""

    VERSION = 0
    MINOR_VERSION = 3

    task_one_configure: asyncio.Task | None = None
    task_two_pair: asyncio.Task | None = None

    def __init__(self) -> None:
        """Init config flow."""
        self._data: dict[str, Any] = {}
        self._pki_list = []
        self._config_directory = Path()
        self._QolsysPanel = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: QolsysPanelConfigEntry):
        return QolsysPanelOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        self._config_directory = Path(self.hass.config.config_dir + "/qolsys_panel/")
        self._QolsysPanel = qolsys_controller()
        self._QolsysPanel.settings.config_directory = self._config_directory.resolve()
        self._QolsysPanel.settings.log_mqtt_mesages = False

        return self.async_show_menu(
            step_id="user",
            menu_options={
                "pki_autodiscovery_1": "Automatic Panel Discovery and Pairing",
                "existing_pki": "Use Existing PKI",
            },
        )

    async def async_step_pki_autodiscovery_1(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the pki_autodiscovery step - User message."""
        _LOGGER.debug("pki_autodiscovery_1: User information")

        if self._QolsysPanel is not None:
            self._QolsysPanel.settings.plugin_ip = await get_local_ip(hass=self.hass)
            self._QolsysPanel.settings.panel_ip = ""
            self._QolsysPanel.settings.random_mac = ""
            self._QolsysPanel.settings.auto_discover_pki = True

        if user_input is None:
            return self.async_show_form(
                step_id="pki_autodiscovery_1",
            )

        return await self.async_step_pki_autodiscovery_2()

    async def async_step_pki_autodiscovery_2(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the pki_autodiscovery step 2 - Load Plugin."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="pki_autodiscovery_2",
            )

        if not await self._QolsysPanel.config(start_pairing=True):
            _LOGGER.error("Error configuring and pairing with plugin")
            errors["base"] = "Error configuring and pairing with plugin"
            await self._QolsysPanel.stop_operation()
            return self.async_show_form(
                step_id="pki_autodiscovery_2",
                data_schema=None,
                errors=errors,
            )

        try:
            await self._QolsysPanel.mqtt_connect_task(
                reconnect=False, run_forever=False
            )
        except QolsysSslError:
            _LOGGER.debug("Error connecting to panel - TLS Certificate Error")
            errors["base"] = "Error connecting to panel - TLS Certificate Error"
            await self._QolsysPanel.stop_operation()
            return self.async_show_form(
                step_id="pki_autodiscovery_2",
                data_schema=None,
                errors=errors,
            )
        finally:
            await self._QolsysPanel.stop_operation()
            _LOGGER.debug("Plugin is configured")

        # Add entry to Home Assistant
        await self.async_set_unique_id(format_mac(self._QolsysPanel.panel.MAC_ADDRESS))
        self._abort_if_unique_id_configured()

        self._data[CONF_MAC] = format_mac(self._QolsysPanel.panel.MAC_ADDRESS)
        self._data[CONF_HOST] = self._QolsysPanel.settings.panel_ip
        self._data[CONF_MODEL] = self._QolsysPanel.panel.product_type
        self._data[CONF_RANDOM_MAC] = format_mac(self._QolsysPanel.settings.random_mac)
        self._data[CONF_IMEI] = self._QolsysPanel.panel.imei
        await self._QolsysPanel.stop_operation()

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
        path = self._config_directory.joinpath("pki")

        directories = [p.name for p in path.iterdir() if p.is_dir()]
        for d in directories:
            self._pki_list.append(":".join(d[i : i + 2] for i in range(0, len(d), 2)))

        data_schema = {
            vol.Required(CONF_HOST): str,
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
            await self._QolsysPanel.stop_operation()
            return self.async_show_form(
                step_id="existing_pki",
                data_schema=vol.Schema(data_schema),
                errors=errors,
            )

        if user_input is None:
            return self.async_show_form(
                step_id="existing_pki", data_schema=vol.Schema(data_schema)
            )

        self._QolsysPanel.settings.plugin_ip = await get_local_ip(hass=self.hass)
        self._QolsysPanel.settings.panel_ip = user_input[CONF_HOST]
        self._QolsysPanel.settings.random_mac = user_input[CONF_RANDOM_MAC]
        self._QolsysPanel.settings.auto_discover_pki = False

        # Check if PKI is valid
        self._QolsysPanel._pki.set_id(user_input[CONF_RANDOM_MAC])
        if (
            not self._QolsysPanel._pki.check_key_file()
            or not self._QolsysPanel._pki.check_cer_file()
            or not self._QolsysPanel._pki.check_csr_file()
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
            self._QolsysPanel.stop_operation()
            return self.async_show_form(
                step_id="existing_pki",
                data_schema=vol.Schema(data_schema),
                errors=errors,
            )

        if not await self._QolsysPanel.config(start_pairing=True):
            _LOGGER.error("Error configuring and pairing with plugin")
            errors["base"] = "Error configuring and pairing with plugin"
            self._QolsysPanel.stop_operation()
            return self.async_show_form(
                step_id="pki_autodiscovery_2",
                data_schema=None,
                errors=errors,
            )

        try:
            await self._QolsysPanel.mqtt_connect_task(
                reconnect=False, run_forever=False
            )
        except QolsysSslError:
            _LOGGER.debug("Error connecting to panel - TLS Certificate Error")
            errors["base"] = "Error connecting to panel - TLS Certificate Error"
            self._QolsysPanel.stop_operation()
            return self.async_show_form(
                step_id="pki_autodiscovery_2",
                data_schema=None,
                errors=errors,
            )
        finally:
            _LOGGER.debug("Plugin is configured")

        # Add entry to Home Assistant
        await self.async_set_unique_id(format_mac(self._QolsysPanel.panel.MAC_ADDRESS))
        self._abort_if_unique_id_configured()

        self._data[CONF_MAC] = format_mac(self._QolsysPanel.panel.MAC_ADDRESS)
        self._data[CONF_HOST] = self._QolsysPanel.settings.panel_ip
        self._data[CONF_MODEL] = self._QolsysPanel.panel.product_type
        self._data[CONF_RANDOM_MAC] = format_mac(self._QolsysPanel.settings.random_mac)
        self._data[CONF_IMEI] = self._QolsysPanel.panel.imei

        await self._QolsysPanel.stop_operation()

        return self.async_create_entry(
            title=f"Qolsys Panel ({self._data[CONF_MAC]})",
            data=self._data,
        )


# Options Flow Handler
class QolsysPanelOptionsFlowHandler(OptionsFlowWithReload):
    """Handle Qolsys Panel options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options

        data_schema = vol.Schema(
            {
                vol.Required(
                    OPTION_ARM_CODE,
                    default=options.get(OPTION_ARM_CODE, DEFAULT_ARM_CODE_REQUIRED),
                ): bool,
                vol.Required(
                    OPTION_TRIGGER_POLICE,
                    default=options.get(OPTION_TRIGGER_POLICE, DEFAULT_TRIGGER_POLICE),
                ): bool,
                vol.Required(
                    OPTION_TRIGGER_AUXILLIARY,
                    default=options.get(
                        OPTION_TRIGGER_AUXILLIARY,
                        DEFAULT_TRIGGER_AUXILLIARY,
                    ),
                ): bool,
                vol.Required(
                    OPTION_TRIGGER_FIRE,
                    default=options.get(OPTION_TRIGGER_FIRE, DEFAULT_TRIGGER_FIRE),
                ): bool,
                vol.Required(
                    OPTION_MOTION_SENSOR_DELAY_ENABLED,
                    default=options.get(
                        OPTION_MOTION_SENSOR_DELAY_ENABLED,
                        DEFAULT_MOTION_SENSOR_DELAY_ENABLED,
                    ),
                ): bool,
                vol.Required(
                    OPTION_MOTION_SENSOR_DELAY,
                    default=options.get(
                        OPTION_MOTION_SENSOR_DELAY,
                        DEFAULT_MOTION_SENSOR_DELAY,
                    ),
                ): int,
            },
            extra=vol.PREVENT_EXTRA,
        )

        _LOGGER.debug(data_schema)

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )
