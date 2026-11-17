"""Shared fixtures for the Qolsys Panel tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from qolsys_controller.enum_qolsys import ZoneStatus
from qolsys_controller.zone import QolsysZone

from custom_components.qolsys_panel.const import CONF_IMEI, CONF_RANDOM_MAC, DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL

pytest_plugins = "pytest_homeassistant_custom_component"

PANEL_MAC = "aa:bb:cc:dd:ee:ff"
PANEL_HOST = "192.168.1.50"
PANEL_MODEL = "IQ Panel 4"
PANEL_IMEI = "123456789012345"
RANDOM_MAC = "aa:bb:cc:dd:ee:01"
PLUGIN_IP = "192.168.1.2"


def set_zone_status(zone: MagicMock, status: ZoneStatus) -> None:
    """Set a mocked zone's status and answer status checks with the real logic."""
    zone.sensorstatus = status
    zone.is_trouble.side_effect = lambda: QolsysZone.is_trouble(zone)
    zone.is_tampered.side_effect = lambda: QolsysZone.is_tampered(zone)
    zone.is_available_reading.side_effect = lambda: QolsysZone.is_available_reading(
        zone
    )
    zone.is_available_status.side_effect = lambda: QolsysZone.is_available_status(zone)
    zone.is_available_tamper.side_effect = lambda: QolsysZone.is_available_tamper(zone)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in all tests."""
    return


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent the integration from actually being set up."""
    with (
        patch(
            "custom_components.qolsys_panel.async_setup_entry", return_value=True
        ) as mock_setup,
        patch("custom_components.qolsys_panel.async_unload_entry", return_value=True),
    ):
        yield mock_setup


@pytest.fixture
def mock_qolsys_controller() -> Generator[MagicMock]:
    """Mock the qolsys_controller instance used by the config flow."""
    controller = MagicMock()
    controller.run_forever = AsyncMock()
    controller.stop = AsyncMock()
    controller.is_paired = AsyncMock(return_value=True)

    controller._pki.check_key_file = AsyncMock(return_value=True)
    controller._pki.check_secure_file = AsyncMock(return_value=True)
    controller._pki.check_qolsys_cer_file = AsyncMock(return_value=True)

    controller.settings.check_panel_ip = MagicMock(return_value=True)
    controller.settings.check_plugin_ip = MagicMock(return_value=True)

    controller.panel.MAC_ADDRESS = PANEL_MAC
    controller.panel.product_type = PANEL_MODEL
    controller.panel.imei = PANEL_IMEI

    with (
        patch(
            "custom_components.qolsys_panel.config_flow.qolsys_controller",
            return_value=controller,
        ),
        patch(
            "custom_components.qolsys_panel.config_flow.get_local_ip",
            return_value=PLUGIN_IP,
        ),
    ):
        yield controller


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Qolsys Panel ({PANEL_MAC})",
        data={
            CONF_HOST: PANEL_HOST,
            CONF_MAC: PANEL_MAC,
            CONF_MODEL: PANEL_MODEL,
            CONF_IMEI: PANEL_IMEI,
            CONF_RANDOM_MAC: RANDOM_MAC,
        },
        unique_id=PANEL_MAC,
        version=1,
        minor_version=0,
    )
