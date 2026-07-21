"""Tests for the Qolsys Panel utilities."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant

from custom_components.qolsys_panel.utils import get_local_ip

ADAPTERS_PATH = "custom_components.qolsys_panel.utils.network.async_get_adapters"


async def test_get_local_ip_returns_default_adapter(hass: HomeAssistant) -> None:
    """The default adapter's IPv4 address is returned."""
    adapters = [
        {"default": False, "ipv4": [{"address": "10.0.0.1"}]},
        {"default": True, "ipv4": [{"address": "192.168.1.9"}]},
    ]
    with patch(ADAPTERS_PATH, AsyncMock(return_value=adapters)):
        assert await get_local_ip(hass) == "192.168.1.9"


async def test_get_local_ip_no_default_adapter(hass: HomeAssistant) -> None:
    """With no default adapter, an empty string is returned."""
    adapters = [{"default": False, "ipv4": [{"address": "10.0.0.1"}]}]
    with patch(ADAPTERS_PATH, AsyncMock(return_value=adapters)):
        assert await get_local_ip(hass) == ""
