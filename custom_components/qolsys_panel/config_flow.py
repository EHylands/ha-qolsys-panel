"""Config flow for Qolsys Panel integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from pathlib import Path
import re
from ssl import SSLError
from typing import Any

from qolsys_controller import qolsys_controller
from qolsys_controller.errors import QolsysConfigError, QolsysMqttError, QolsysSslError
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import selector
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import (
    CONF_IMEI,
    CONF_RANDOM_MAC,
    CONFIG_DIR,
    DEFAULT_ARM_CODE_REQUIRED,
    DEFAULT_DISARM_CODE_REQUIRED,
    DEFAULT_MOTION_SENSOR_DELAY,
    DEFAULT_MOTION_SENSOR_DELAY_ENABLED,
    DEFAULT_TRIGGER_AUXILLIARY,
    DEFAULT_TRIGGER_FIRE,
    DEFAULT_TRIGGER_POLICE,
    DOMAIN,
    OPTION_ARM_CODE,
    OPTION_DISARM_CODE,
    OPTION_MOTION_SENSOR_DELAY,
    OPTION_MOTION_SENSOR_DELAY_ENABLED,
    OPTION_TRIGGER_AUXILLIARY,
    OPTION_TRIGGER_FIRE,
    OPTION_TRIGGER_POLICE,
)
from .types import QolsysPanelConfigEntry
from .utils import get_local_ip

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)
_qolsys_controller_logger = logging.getLogger("qolsys_controller")
getattr(
    _qolsys_controller_logger,
    "orig_setLevel",
    _qolsys_controller_logger.setLevel,
)(logging.DEBUG)


def _leaf_message(exc: BaseException) -> str:
    # Return the message of the first leaf exception inside an ExceptionGroup
    while isinstance(exc, BaseExceptionGroup):
        exc = exc.exceptions[0]
    return str(exc)


_MAC_DIR_NAME_RE = re.compile(r"[0-9A-Fa-f]{12}")

# _try_connect error codes that mean a failed connection/pairing attempt (as opposed
# to fixable user input such as a bad host or an incomplete PKI selection).
_CONNECTION_FAILURE_ERRORS = {
    "authentication_failed",
    "cannot_connect",
    "configuration_error",
    "unknown",
}


class QolsysPanelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Qolsys Panel."""

    VERSION = 1
    MINOR_VERSION = 0

    def __init__(self) -> None:
        """Init config flow."""
        self._data: dict[str, Any] = {}
        self._pki_list: list[str] = []
        self._QolsysPanel = qolsys_controller()
        self._config_directory = Path()
        self._error_placeholders: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: QolsysPanelConfigEntry,
    ) -> QolsysPanelOptionsFlowHandler:
        return QolsysPanelOptionsFlowHandler()

    async def _async_get_pki_dir(self) -> list[str]:
        pki_list: list[str] = []
        path = self._config_directory.joinpath("pki")

        def _scan() -> list[str]:
            if not path.exists():
                return []
            return [p.name for p in path.iterdir() if p.is_dir()]

        directories = await self.hass.async_add_executor_job(_scan)
        for d in directories:
            if not _MAC_DIR_NAME_RE.fullmatch(d):
                _LOGGER.debug("Ignoring non-MAC PKI directory: %s", d)
                continue
            pki_list.append(":".join(d[i : i + 2] for i in range(0, len(d), 2)))

        return pki_list

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery of a Qolsys Panel via DHCP."""
        mac = format_mac(discovery_info.macaddress)
        _LOGGER.debug(
            "DHCP discovery: host=%s hostname=%s raw_mac=%s formatted_mac=%s",
            discovery_info.ip,
            discovery_info.hostname,
            discovery_info.macaddress,
            mac,
        )

        # IQ2+ panels report their MAC with a trailing newline that
        # format_mac() cannot strip, so a configured entry may carry a
        # "\n"-suffixed unique_id. Match on the stripped form but reuse the
        # entry's *existing* unique_id for the abort check below; never rewrite
        # it, since every entity and device id is derived from it and changing
        # it would re-create them under new ids and break automations.
        unique_id = mac
        for entry in self._async_current_entries(include_ignore=False):
            if entry.unique_id is not None and entry.unique_id.strip() == mac:
                unique_id = entry.unique_id
                break

        # Log the MAC we discovered next to each configured entry's unique_id
        # AND its CONF_MAC data field, so a mismatch (which would re-offer a
        # configured panel) is visible in the logs. The abort is decided on
        # unique_id; logging CONF_MAC too surfaces any divergence between them.
        configured = {
            entry.unique_id: {
                "conf_mac": entry.data.get(CONF_MAC),
                "host": entry.data.get(CONF_HOST),
            }
            for entry in self._async_current_entries(include_ignore=False)
        }
        _LOGGER.debug(
            "DHCP discovery: discovered_mac=%s configured_entries=%s -> %s",
            mac,
            configured,
            "match (will update host and abort)"
            if unique_id != mac or mac in configured
            else "no match (proceeding to setup menu)",
        )

        await self.async_set_unique_id(unique_id)
        # Update the stored host if the panel is already configured, then abort.
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})

        # Remember what discovery told us so the pairing steps can pre-fill it.
        self._data[CONF_MAC] = mac
        self._data[CONF_HOST] = discovery_info.ip
        self.context["title_placeholders"] = {"name": f"Qolsys Panel ({mac})"}

        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the initial menu."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["pki_autodiscovery_1", "existing_pki"],
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
        result = await self._try_connect(
            step="pki_autodiscovery_2",
            host="",
            random_mac="",
            resume_pairing=True,
            start_pairing=True,
        )
        if result != {}:
            # Pairing failed: stop the controller and interrupt the flow
            return await self._async_abort_pairing_failed(result)

        return await self._async_finish()

    async def async_step_existing_pki(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the existing_pki step."""
        self._config_directory = Path(self.hass.config.config_dir) / CONFIG_DIR
        self._pki_list = await self._async_get_pki_dir()

        host_default = self._data.get(CONF_HOST)
        data_schema = {
            (
                vol.Required(CONF_HOST, default=host_default)
                if host_default
                else vol.Required(CONF_HOST)
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

        # No PKI available: nothing the user enters here can be submitted, so
        # show the error alone rather than a host/PKI form with an empty,
        # unusable dropdown.
        if not self._pki_list:
            await self._QolsysPanel.stop()
            return self.async_show_form(
                step_id="existing_pki",
                data_schema=None,
                errors={"base": "no_pki_found"},
            )

        if user_input is None:
            return self.async_show_form(
                step_id="existing_pki", data_schema=vol.Schema(data_schema)
            )

        # User has submitted new data, attempt to reconfigure with new settings
        result = await self._try_connect(
            step="existing_pki",
            host=user_input[CONF_HOST],
            random_mac=user_input[CONF_RANDOM_MAC],
            resume_pairing=False,
            start_pairing=False,
        )
        if result != {}:
            if result["base"] in _CONNECTION_FAILURE_ERRORS:
                # Connection/pairing failure: interrupt the flow.
                return await self._async_abort_pairing_failed(result)
            # Fixable input error (bad host / incomplete PKI): let the user correct it.
            return self.async_show_form(
                step_id="existing_pki",
                data_schema=vol.Schema(data_schema),
                errors=result,
                description_placeholders=self._error_placeholders,
            )

        return await self._async_finish()

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

        # No PKI available: nothing the user enters here can be submitted, so
        # show the error alone rather than a host/PKI form with an empty,
        # unusable dropdown.
        if not self._pki_list:
            await self._QolsysPanel.stop()
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=None,
                errors={"base": "no_pki_found"},
            )

        # No user input, show form to reconfigure settings
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(data_schema),
            )

        # User has submitted new data, attempt to reconfigure with new settings
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
                description_placeholders=self._error_placeholders,
            )

        return await self._async_finish()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication after the panel rejects the client certificate."""
        # Pre-fill the host from the existing entry so the existing-PKI form is
        # populated; the pairing path ignores it.
        host = entry_data.get(CONF_HOST)
        if host:
            self._data[CONF_HOST] = host
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose how to re-authenticate with the panel."""
        return self.async_show_menu(
            step_id="reauth_confirm",
            menu_options=["pki_autodiscovery_1", "existing_pki"],
        )

    async def _async_finish(self) -> ConfigFlowResult:
        """Create the entry, or update the existing one on reauth/reconfigure.

        The pairing and existing-PKI steps are shared across the initial setup,
        reconfigure, and reauth sources; the finalization differs only in how the
        result is committed, so it is centralized here and branches on the flow
        source. Reauth and reconfigure must land on the *same* physical panel, so
        they guard on a unique_id match before updating the entry in place.
        """
        mac = self._data[CONF_MAC]

        # An incomplete pairing can still "succeed" (reach CONNECTED) before the panel
        # reports its identity or writes all PKI artifacts. Creating an entry then yields
        # an empty unique_id / a half-paired entry stuck retrying setup, so refuse it and
        # interrupt the flow instead.
        incomplete_reason = ""
        if not mac:
            incomplete_reason = "the panel did not report its identity (MAC address)"
        elif not await self._QolsysPanel.is_paired():
            incomplete_reason = "pairing did not produce the required certificates"

        if incomplete_reason:
            _LOGGER.error(
                "Pairing incomplete (%s); aborting instead of creating an entry",
                incomplete_reason,
            )
            await self._QolsysPanel.stop()
            return self.async_abort(
                reason="pairing_failed",
                description_placeholders={"reason": incomplete_reason},
            )

        if self.source in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
            entry = (
                self._get_reauth_entry()
                if self.source == SOURCE_REAUTH
                else self._get_reconfigure_entry()
            )
            # IQ2+ panels can report a MAC with a trailing newline, so an entry's
            # stored unique_id may be "\n"-suffixed while a fresh connection
            # yields a clean MAC. Match on the stripped form but reuse the entry's
            # existing unique_id so the guard below does not fire on a purely
            # cosmetic difference and re-create every entity (see async_step_dhcp).
            unique_id = mac
            if entry.unique_id is not None and entry.unique_id.strip() == mac.strip():
                unique_id = entry.unique_id
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(entry, data_updates=self._data)

        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"Qolsys Panel ({mac})",
            data=self._data,
        )

    async def _async_abort_pairing_failed(
        self, result: dict[str, str]
    ) -> ConfigFlowResult:
        """Stop the controller and interrupt the flow with the specific failure reason."""
        await self._QolsysPanel.stop()
        reason_text = self._error_placeholders.get("reason") or result["base"]
        return self.async_abort(
            reason="pairing_failed",
            description_placeholders={"reason": reason_text},
        )

    async def _try_connect(
        self,
        step: str,
        host: str,
        random_mac: str,
        resume_pairing: bool = False,
        start_pairing: bool = False,
    ) -> dict[str, str]:
        self._error_placeholders = {}
        self._QolsysPanel.settings.config_directory = str(
            self._config_directory.resolve()
        )
        self._QolsysPanel.settings.panel_ip = host
        self._QolsysPanel.settings.plugin_ip = await get_local_ip(hass=self.hass)
        self._QolsysPanel.settings.random_mac = random_mac
        self._QolsysPanel.settings.auto_discover_pki = False
        self._QolsysPanel.settings.pairing_resume = resume_pairing
        self._QolsysPanel.settings.mqtt_bridge_enabled = False
        self._QolsysPanel._pki.set_id(random_mac)

        # if start_pairing is True, set home assistant zeroconf shared instance
        if start_pairing:
            zc = await zeroconf.async_get_async_instance(self.hass)
            self._QolsysPanel.settings.shared_zeroconf_instance = zc

        # PKI files and panel IP are only relevant once pairing has produced
        # them; skip these checks while start_pairing is in progress.
        if not start_pairing:
            # Check is private key exists
            if not await self._QolsysPanel._pki.check_key_file():
                _LOGGER.error("Private key file not found for PKI: %s", random_mac)
                self._error_placeholders = {"random_mac": random_mac}
                return {"base": "private_key_not_found"}

            # Check client certificate exists
            if not await self._QolsysPanel._pki.check_secure_file():
                _LOGGER.error(
                    "Client certificate file not found for PKI: %s", random_mac
                )
                self._error_placeholders = {"random_mac": random_mac}
                return {"base": "client_certificate_not_found"}

            # Check Qolsys public certificate exists
            if not await self._QolsysPanel._pki.check_qolsys_cer_file():
                _LOGGER.error(
                    "Qolsys certificate file not found for PKI: %s", random_mac
                )
                self._error_placeholders = {"random_mac": random_mac}
                return {"base": "qolsys_certificate_not_found"}

            # Check if panel IP is valid
            if not self._QolsysPanel.settings.check_panel_ip():
                _LOGGER.error(
                    "Invalid Panel IP: %s", self._QolsysPanel.settings.panel_ip
                )
                self._error_placeholders = {
                    "panel_ip": self._QolsysPanel.settings.panel_ip
                }
                return {"base": "invalid_panel_ip"}

        # Check if plugin IP is valid
        if not self._QolsysPanel.settings.check_plugin_ip():
            _LOGGER.error("Invalid Plugin IP: %s", self._QolsysPanel.settings.plugin_ip)
            self._error_placeholders = {
                "plugin_ip": self._QolsysPanel.settings.plugin_ip
            }
            return {"base": "invalid_plugin_ip"}

        # Attempt to connect to panel with provided settings
        error = {}
        try:
            await self._QolsysPanel.run_forever(
                reconnect=False, run_once=True, start_pairing=start_pairing
            )
        except* (QolsysSslError, SSLError) as eg:
            _LOGGER.error("TLS error during step: %s", step)
            self._error_placeholders = {"reason": _leaf_message(eg)}
            error = {"base": "authentication_failed"}

        except* QolsysMqttError as eg:
            _LOGGER.error("Error connecting to panel during step: %s", step)
            self._error_placeholders = {"reason": _leaf_message(eg)}
            error = {"base": "cannot_connect"}

        except* QolsysConfigError as eg:
            _LOGGER.error("Qolsys Panel Configuration Error during step: %s", step)
            self._error_placeholders = {"reason": _leaf_message(eg)}
            error = {"base": "configuration_error"}

        except* Exception as eg:
            _LOGGER.exception("Unexpected error during step: %s", step)
            self._error_placeholders = {"reason": _leaf_message(eg)}
            error = {"base": "unknown"}

        if error != {}:
            return error

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
                    OPTION_DISARM_CODE,
                    default=options.get(
                        OPTION_DISARM_CODE, DEFAULT_DISARM_CODE_REQUIRED
                    ),
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
