"""Tests for the Qolsys Panel config flow."""

from collections.abc import Iterable
from pathlib import Path
from ssl import SSLError
from typing import cast
from unittest.mock import AsyncMock, MagicMock

from conftest import (
    PANEL_HOST,
    PANEL_IMEI,
    PANEL_MAC,
    PANEL_MODEL,
    PLUGIN_IP,
    RANDOM_MAC,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from qolsys_controller.errors import QolsysConfigError, QolsysMqttError, QolsysSslError

from custom_components.qolsys_panel.const import (
    CONF_IMEI,
    CONF_RANDOM_MAC,
    DOMAIN,
    OPTION_ARM_CODE,
    OPTION_DISARM_CODE,
    OPTION_MOTION_SENSOR_DELAY,
    OPTION_MOTION_SENSOR_DELAY_ENABLED,
    OPTION_TRIGGER_AUXILLIARY,
    OPTION_TRIGGER_FIRE,
    OPTION_TRIGGER_POLICE,
)
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

# PKI folders on disk are the random MAC without separators
PKI_DIR_NAME = RANDOM_MAC.replace(":", "")

NO_PKI_ERROR = "no_pki_found"

EXPECTED_ENTRY_DATA = {
    CONF_MAC: PANEL_MAC,
    CONF_HOST: PANEL_HOST,
    CONF_MODEL: PANEL_MODEL,
    CONF_IMEI: PANEL_IMEI,
    CONF_RANDOM_MAC: RANDOM_MAC,
}

EXISTING_PKI_USER_INPUT = {
    CONF_HOST: PANEL_HOST,
    CONF_RANDOM_MAC: RANDOM_MAC,
}


@pytest.fixture(autouse=True)
def _zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Mock zeroconf: the integration manifest depends on it."""


@pytest.fixture
def tmp_config_dir(hass: HomeAssistant, tmp_path: Path) -> Path:
    """Point the Home Assistant config dir at an empty temporary directory."""
    hass.config.config_dir = str(tmp_path)
    return tmp_path


@pytest.fixture
def pki_dir(tmp_config_dir: Path) -> Path:
    """Create an existing PKI directory in the config dir."""
    path: Path = tmp_config_dir / "qolsys_panel" / "pki" / PKI_DIR_NAME
    path.mkdir(parents=True)
    return path


async def _start_menu_step(hass: HomeAssistant, next_step_id: str):
    """Start a user flow and select a menu option."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": next_step_id}
    )


async def test_user_menu(hass: HomeAssistant, mock_qolsys_controller: MagicMock):
    """Test the initial user step shows the menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert set(cast("Iterable[str]", result["menu_options"])) == {
        "pki_autodiscovery_1",
        "existing_pki",
    }


DISCOVERY_IP = "192.168.1.77"
# DHCP reports the MAC without separators; it normalises back to PANEL_MAC.
PANEL_MAC_NO_SEP = PANEL_MAC.replace(":", "")


def _dhcp_info(macaddress: str, ip: str = DISCOVERY_IP) -> DhcpServiceInfo:
    """Build a DHCP discovery payload."""
    return DhcpServiceInfo(ip=ip, hostname="qolsys", macaddress=macaddress)


async def test_dhcp_discovery_shows_menu(
    hass: HomeAssistant, mock_qolsys_controller: MagicMock
):
    """A newly discovered panel routes DHCP discovery into the setup menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=_dhcp_info("3c317800abcd"),
    )

    assert result["type"] is FlowResultType.MENU
    assert set(cast("Iterable[str]", result["menu_options"])) == {
        "pki_autodiscovery_1",
        "existing_pki",
    }


async def test_dhcp_discovery_updates_host_and_aborts(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
):
    """Re-discovering a configured panel updates its host and aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=_dhcp_info(PANEL_MAC_NO_SEP, ip="192.168.1.99"),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.99"


async def test_dhcp_discovery_matches_newline_suffixed_unique_id(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_setup_entry: AsyncMock,
):
    r"""IQ2+ panels store the MAC with a trailing newline; discovery still matches.

    The clean MAC from DHCP must abort against the "\n"-suffixed entry, and the
    entry's unique_id must be left untouched (every entity/device id is derived
    from it, so changing it would re-create them and break automations).
    """
    dirty_unique_id = f"{PANEL_MAC}\n"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Qolsys Panel ({PANEL_MAC})",
        data={
            CONF_HOST: PANEL_HOST,
            CONF_MAC: dirty_unique_id,
            CONF_MODEL: PANEL_MODEL,
            CONF_IMEI: PANEL_IMEI,
            CONF_RANDOM_MAC: RANDOM_MAC,
        },
        unique_id=dirty_unique_id,
        version=1,
        minor_version=0,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=_dhcp_info(PANEL_MAC_NO_SEP, ip="192.168.1.99"),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Host refreshed, but the newline-suffixed unique_id is preserved untouched.
    assert entry.data[CONF_HOST] == "192.168.1.99"
    assert entry.unique_id == dirty_unique_id


async def test_dhcp_discovery_prefills_existing_pki_host(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    pki_dir: Path,
):
    """The discovered host is the default in the existing PKI step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=_dhcp_info("3c317800abcd"),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "existing_pki"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "existing_pki"
    data_schema = result["data_schema"]
    assert data_schema is not None
    host_key = next(k for k in data_schema.schema if k == CONF_HOST)
    assert host_key.default() == DISCOVERY_IP


async def test_existing_pki_ignores_non_mac_directories(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    pki_dir: Path,
):
    """Non-MAC-shaped directories in the pki folder are excluded from the dropdown."""
    (pki_dir.parent / ".DS_Store").mkdir()

    result = await _start_menu_step(hass, "existing_pki")

    assert result["type"] is FlowResultType.FORM
    data_schema = result["data_schema"]
    assert data_schema is not None
    random_mac_key = next(k for k in data_schema.schema if k == CONF_RANDOM_MAC)
    options = data_schema.schema[random_mac_key].config["options"]
    assert options == [RANDOM_MAC]


async def test_pki_autodiscovery_flow(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_setup_entry: AsyncMock,
):
    """Test the full automatic discovery and pairing flow."""
    result = await _start_menu_step(hass, "pki_autodiscovery_1")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pki_autodiscovery_1"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pki_autodiscovery_2"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Qolsys Panel ({PANEL_MAC})"
    assert result["data"] == {
        CONF_MAC: PANEL_MAC,
        CONF_HOST: "",
        CONF_MODEL: PANEL_MODEL,
        CONF_IMEI: PANEL_IMEI,
        CONF_RANDOM_MAC: "",
    }
    assert result["result"].unique_id == PANEL_MAC
    mock_qolsys_controller.run_forever.assert_awaited_once_with(
        reconnect=False, run_once=True, start_pairing=True
    )
    assert len(mock_setup_entry.mock_calls) == 1


async def test_pki_autodiscovery_error_and_recover(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_setup_entry: AsyncMock,
):
    """Test pairing shows an error on failure and can recover."""
    result = await _start_menu_step(hass, "pki_autodiscovery_1")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    mock_qolsys_controller.run_forever.side_effect = QolsysMqttError("boom")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pki_autodiscovery_2"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_qolsys_controller.run_forever.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_pki_autodiscovery_duplicate_aborts(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_config_entry: MockConfigEntry,
):
    """Test pairing aborts when the panel is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await _start_menu_step(hass, "pki_autodiscovery_1")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_existing_pki_flow(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_setup_entry: AsyncMock,
    pki_dir: Path,
):
    """Test the full existing PKI flow."""
    result = await _start_menu_step(hass, "existing_pki")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "existing_pki"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EXISTING_PKI_USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Qolsys Panel ({PANEL_MAC})"
    assert result["data"] == EXPECTED_ENTRY_DATA
    assert result["result"].unique_id == PANEL_MAC
    mock_qolsys_controller.run_forever.assert_awaited_once_with(
        reconnect=False, run_once=True, start_pairing=False
    )
    assert len(mock_setup_entry.mock_calls) == 1


async def test_existing_pki_no_pki_found(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    tmp_config_dir: Path,
):
    """Test the existing PKI step when no PKI directory exists."""
    result = await _start_menu_step(hass, "existing_pki")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "existing_pki"
    assert result["errors"] == {"base": NO_PKI_ERROR}
    mock_qolsys_controller.stop.assert_awaited_once()


@pytest.mark.parametrize(
    ("target", "check", "error", "placeholders"),
    [
        ("_pki", "check_key_file", "private_key_not_found", {"random_mac": RANDOM_MAC}),
        (
            "_pki",
            "check_secure_file",
            "client_certificate_not_found",
            {"random_mac": RANDOM_MAC},
        ),
        (
            "_pki",
            "check_qolsys_cer_file",
            "qolsys_certificate_not_found",
            {"random_mac": RANDOM_MAC},
        ),
        ("settings", "check_panel_ip", "invalid_panel_ip", {"panel_ip": PANEL_HOST}),
        ("settings", "check_plugin_ip", "invalid_plugin_ip", {"plugin_ip": PLUGIN_IP}),
    ],
)
async def test_existing_pki_validation_errors(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_setup_entry: AsyncMock,
    pki_dir: Path,
    *,
    target: str,
    check: str,
    error: str,
    placeholders: dict[str, str],
):
    """Test PKI and IP validation errors, then recover."""
    mock_check = getattr(getattr(mock_qolsys_controller, target), check)
    mock_check.return_value = False

    result = await _start_menu_step(hass, "existing_pki")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EXISTING_PKI_USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "existing_pki"
    assert result["errors"] == {"base": error}
    assert result["description_placeholders"] == placeholders

    mock_check.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EXISTING_PKI_USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (QolsysSslError("boom"), "authentication_failed"),
        (SSLError(), "authentication_failed"),
        (QolsysMqttError("boom"), "cannot_connect"),
        (QolsysConfigError("boom"), "configuration_error"),
    ],
)
async def test_existing_pki_connection_errors(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_setup_entry: AsyncMock,
    pki_dir: Path,
    *,
    side_effect: Exception,
    error: str,
):
    """Test connection errors during the existing PKI flow, then recover."""
    mock_qolsys_controller.run_forever.side_effect = side_effect

    result = await _start_menu_step(hass, "existing_pki")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EXISTING_PKI_USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "existing_pki"
    assert result["errors"] == {"base": error}

    mock_qolsys_controller.run_forever.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EXISTING_PKI_USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == EXPECTED_ENTRY_DATA


async def test_existing_pki_duplicate_aborts(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_config_entry: MockConfigEntry,
    pki_dir: Path,
):
    """Test the existing PKI flow aborts when the panel is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await _start_menu_step(hass, "existing_pki")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EXISTING_PKI_USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    pki_dir: Path,
):
    """Test the full reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.60", CONF_RANDOM_MAC: RANDOM_MAC},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.60"


async def test_reconfigure_no_pki_found(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_config_entry: MockConfigEntry,
    tmp_config_dir: Path,
):
    """Test the reconfigure step when no PKI directory exists."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": NO_PKI_ERROR}
    mock_qolsys_controller.stop.assert_awaited_once()


async def test_reconfigure_error_and_recover(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    pki_dir: Path,
):
    """Test the reconfigure flow shows an error on failure and can recover."""
    mock_config_entry.add_to_hass(hass)
    mock_qolsys_controller.run_forever.side_effect = QolsysMqttError("boom")

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EXISTING_PKI_USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_qolsys_controller.run_forever.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EXISTING_PKI_USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_unique_id_mismatch(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_config_entry: MockConfigEntry,
    pki_dir: Path,
):
    """Test the reconfigure flow aborts when a different panel answers."""
    mock_config_entry.add_to_hass(hass)
    mock_qolsys_controller.panel.MAC_ADDRESS = "11:22:33:44:55:66"

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EXISTING_PKI_USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


async def test_reauth_existing_pki_flow(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    pki_dir: Path,
):
    """Reauth via the existing-PKI path updates the entry and reloads."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "existing_pki"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "existing_pki"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.77", CONF_RANDOM_MAC: RANDOM_MAC},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.77"


async def test_reauth_pki_autodiscovery_flow(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
):
    """Reauth via re-pairing generates a fresh PKI and reloads the entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "pki_autodiscovery_1"}
    )
    assert result["step_id"] == "pki_autodiscovery_1"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "pki_autodiscovery_2"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    mock_qolsys_controller.run_forever.assert_awaited_once_with(
        reconnect=False, run_once=True, start_pairing=True
    )


async def test_reauth_unique_id_mismatch(
    hass: HomeAssistant,
    mock_qolsys_controller: MagicMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    pki_dir: Path,
):
    """Reauth aborts when a different panel answers, protecting the entry."""
    mock_config_entry.add_to_hass(hass)
    mock_qolsys_controller.panel.MAC_ADDRESS = "11:22:33:44:55:66"

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "existing_pki"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EXISTING_PKI_USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


async def test_options_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
):
    """Test the options flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    user_input = {
        OPTION_ARM_CODE: True,
        OPTION_DISARM_CODE: True,
        OPTION_TRIGGER_POLICE: True,
        OPTION_TRIGGER_AUXILLIARY: False,
        OPTION_TRIGGER_FIRE: True,
        OPTION_MOTION_SENSOR_DELAY_ENABLED: True,
        OPTION_MOTION_SENSOR_DELAY: 120,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert dict(mock_config_entry.options) == user_input
