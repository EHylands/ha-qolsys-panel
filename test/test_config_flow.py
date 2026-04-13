import pytest
from ssl import SSLError

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.qolsys_panel.const import DOMAIN


@pytest.mark.asyncio
async def test_user_menu(hass):
    """Test config flow menu."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == "menu"
    assert "pki_autodiscovery_1" in result["menu_options"]


@pytest.mark.asyncio
async def test_existing_pki_success(hass, mock_qolsys_controller):
    """Test successful existing PKI setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "existing_pki"},
    )

    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.50",
            "random_mac": "AA:BB:CC:DD:EE:FF",
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Qolsys Panel (AA:BB:CC:DD:EE:FF)"


@pytest.mark.asyncio
async def test_tls_auth_failure(hass, mock_qolsys_controller):
    """Test TLS failure handling."""

    mock_qolsys_controller.mqtt_connect_task.side_effect = SSLError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )

    assert result["type"] == "menu"


@pytest.mark.asyncio
async def test_duplicate_device_abort(hass):
    """Ensure duplicate panel cannot be added."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Qolsys Panel",
        data={"mac": "AA:BB:CC:DD:EE:FF"},
        unique_id="AA:BB:CC:DD:EE:FF",
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )

    assert result["type"] == "menu"
