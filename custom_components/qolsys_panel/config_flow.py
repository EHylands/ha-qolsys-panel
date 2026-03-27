"""Config flow for Qolsys Panel integration."""

from __future__ import annotations

import logging
from pathlib import Path
from ssl import SSLError
from typing import Any

from qolsys_controller import qolsys_controller
from qolsys_controller.errors import QolsysSslError, QolsysMqttError
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


from .types import QolsysPanelConfigEntry

from .const import (
    CONF_IMEI,
    CONF_RANDOM_MAC,
    CONFIG_DIR,
    DEFAULT_ARM_CODE_REQUIRED,
    DEFAULT_TRIGGER_AUXILLIARY,
    DEFAULT_TRIGGER_FIRE,
    DEFAULT_TRIGGER_POLICE,
    DEFAULT_MOTION_SENSOR_DELAY,
    DEFAULT_MOTION_SENSOR_DELAY_ENABLED,
    DOMAIN,
    OPTION_ARM_CODE,
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

    def __init__(self) -> None:
        """Init config flow."""
        self._data: dict[str, Any] = {}
        self._pki_list: list[str] = []
        self._QolsysPanel = qolsys_controller()
        self._QolsysPanel.settings.log_mqtt_messages = False
        self._config_directory = Path()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: QolsysPanelConfigEntry):
        return QolsysPanelOptionsFlowHandler()

    async def _async_get_pki_dir(self) -> list[str]:
        pki_list: list[str] = []
        path = self._config_directory.joinpath("pki")

        def _scan():
            if not path.exists():
                return []
            return [p.name for p in path.iterdir() if p.is_dir()]

        directories = await self.hass.async_add_executor_job(_scan)
        for d in directories:
            pki_list.append(":".join(d[i : i + 2] for i in range(0, len(d), 2)))

        return pki_list

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the initial menu."""
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
        self._config_directory = Path(self.hass.config.config_dir) / CONFIG_DIR

        if user_input is None:
            return self.async_show_form(
                step_id="pki_autodiscovery_1",
            )
        return await self.async_step_pki_autodiscovery_2()

    async def async_step_pki_autodiscovery_2(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the pki_autodiscovery step 2 - Load Plugin."""
        if user_input is None:
            return self.async_show_form(
                step_id="pki_autodiscovery_2",
            )

        # User has submitted new data, attempt to configure with settings
        if user_input is not None:
            result = await self._try_connect(
                step="pki_autodiscovery_2",
                host="",
                random_mac="",
                resume_pairing=True,
                start_pairing=True,
            )
            if result != {}:
                return self.async_show_form(
                    step_id="pki_autodiscovery_2",
                    data_schema=None,
                    errors=result,
                )

        # Add entry to Home Assistant
        await self.async_set_unique_id(self._data[CONF_MAC])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Qolsys Panel ({self._data[CONF_MAC]})",
            data=self._data,
        )

    async def async_step_existing_pki(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the existing_pki step."""
        self._config_directory = Path(self.hass.config.config_dir) / CONFIG_DIR
        self._pki_list = await self._async_get_pki_dir()

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

        # Abort if no PKI available
        if not self._pki_list:
            await self._QolsysPanel.stop_operation()
            return self.async_show_form(
                step_id="existing_pki",
                data_schema=vol.Schema(data_schema),
                errors={"base": "No existing PKI found in configuration folder"},
            )

        if user_input is None:
            return self.async_show_form(
                step_id="existing_pki", data_schema=vol.Schema(data_schema)
            )

        # User has submitted new data, attempt to reconfigure with new settings
        if user_input is not None:
            result = await self._try_connect(
                step="existing_pki",
                host=user_input[CONF_HOST],
                random_mac=user_input[CONF_RANDOM_MAC],
                resume_pairing=False,
                start_pairing=False,
            )
            if result != {}:
                return self.async_show_form(
                    step_id="existing_pki",
                    data_schema=vol.Schema(data_schema),
                    errors=result,
                )

        # Add entry to Home Assistant
        await self.async_set_unique_id(self._data[CONF_MAC])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Qolsys Panel ({self._data[CONF_MAC]})",
            data=self._data,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle  reconfigure flow."""
        entry = self._get_reconfigure_entry()
        self._config_directory = Path(self.hass.config.config_dir) / CONFIG_DIR
        self._pki_list = await self._async_get_pki_dir()

        data_schema = {
            vol.Required(
                CONF_HOST,
                default=entry.data.get(CONF_HOST),
            ): str,
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

        # Abort if no PKI available
        if not self._pki_list:
            await self._QolsysPanel.stop_operation()
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(data_schema),
                errors={"base": "No existing PKI found in configuration folder"},
            )

        # No user input, show form to reconfigure settings
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(data_schema),
            )

        # User has submitted new data, attempt to reconfigure with new settings
        if user_input is not None:
            result = await self._try_connect(
                step="reconfigure",
                host=user_input[CONF_HOST],
                random_mac=user_input[CONF_RANDOM_MAC],
                resume_pairing=False,
                start_pairing=False,
            )
            if result != {}:
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=vol.Schema(data_schema),
                    errors=result,
                )

            await self.async_set_unique_id(self._data[CONF_MAC])
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                entry,
                data_updates=self._data,
            )

    async def _try_connect(
        self,
        step: str,
        host: str,
        random_mac: str,
        resume_pairing: bool = False,
        start_pairing: bool = False,
    ) -> dict[str, str]:
        self._QolsysPanel.settings.config_directory = self._config_directory.resolve()
        self._QolsysPanel.settings.panel_ip = host
        self._QolsysPanel.settings.plugin_ip = await get_local_ip(hass=self.hass)
        self._QolsysPanel.settings.random_mac = random_mac
        self._QolsysPanel.settings.auto_discover_pki = False
        self._QolsysPanel.settings.pairing_resume = resume_pairing
        self._QolsysPanel._pki.set_id(random_mac)

        # Check is private key exists
        if not await self._QolsysPanel._pki.check_key_file() and not start_pairing:
            _LOGGER.error("Private key file not found for PKI: %s", random_mac)
            return {"base": f"Private key file not found for PKI: {random_mac}"}

        # Check client certificate exists
        if not await self._QolsysPanel._pki.check_secure_file() and not start_pairing:
            _LOGGER.error("Client certificate file not found for PKI: %s", random_mac)
            return {"base": f"Client certificate file not found for PKI: {random_mac}"}

        # Check Qolsys public certificate exists
        if not await self._QolsysPanel._pki.check_qolsys_cer_file() and not start_pairing:
            _LOGGER.error("Qolsys certificate file not found for PKI: %s", random_mac)
            return {"base": f"Qolsys certificate file not found for PKI: {random_mac}"}

        # Check if panel IP is valid
        if not self._QolsysPanel.settings.check_panel_ip() and not start_pairing:
            _LOGGER.error("Invalid Panel IP: %s", self._QolsysPanel.settings.panel_ip)
            return {"base": f"Invalid Panel IP: {self._QolsysPanel.settings.panel_ip}"}

        # Check if plugin IP is valid
        if not self._QolsysPanel.settings.check_plugin_ip():
            _LOGGER.error("Invalid Plugin IP: %s", self._QolsysPanel.settings.plugin_ip)
            return {
                "base": f"Invalid Plugin IP: {self._QolsysPanel.settings.plugin_ip}"
            }

        # Configure plugin with provided settings
        try:
            if not await self._QolsysPanel.config(start_pairing=start_pairing):
                _LOGGER.error("Failed to Configure Qolsys Panel during step: %s", step)
                return {"base": "cannot_connect"}
        except (QolsysSslError, SSLError):
            _LOGGER.error("TLS error during configuration in step: %s", step)
            return {"base": "TLS certificate error"}

        # Attempt to connect to panel with provided settings
        try:
            await self._QolsysPanel.mqtt_connect_task(
                reconnect=False, run_forever=False
            )
        except (QolsysSslError, SSLError):
            _LOGGER.error("TLS error during step: %s", step)
            return {"base": "authentication_failed"}

        except QolsysMqttError:
            _LOGGER.error("Error connecting to panel during step: %s", step)
            return {"base": "cannot_connect"}

        finally:
            await self._QolsysPanel.stop_operation()

        self._data[CONF_MAC] = format_mac(self._QolsysPanel.panel.MAC_ADDRESS)
        self._data[CONF_HOST] = self._QolsysPanel.settings.panel_ip
        self._data[CONF_MODEL] = self._QolsysPanel.panel.product_type
        self._data[CONF_IMEI] = self._QolsysPanel.panel.imei
        self._data[CONF_RANDOM_MAC] = format_mac(self._QolsysPanel.settings.random_mac)

        return {}


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

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )
