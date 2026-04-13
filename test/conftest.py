import sys
from unittest.mock import MagicMock
import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.qolsys_panel.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def mock_qolsys_controller():
    """Mock qolsys_controller before integration loads."""

    mock_controller = MagicMock()

    sys.modules["qolsys_controller"] = MagicMock(
        qolsys_controller=MagicMock(return_value=mock_controller)
    )

    yield mock_controller


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Qolsys Panel",
        data={
            "host": "192.168.1.10",
            "mac": "AA:BB:CC:DD:EE:FF",
        },
        unique_id="AA:BB:CC:DD:EE:FF",
    )


@pytest.fixture
async def setup_integration(hass: HomeAssistant, mock_config_entry: MockConfigEntry):
    """Set up the integration."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
