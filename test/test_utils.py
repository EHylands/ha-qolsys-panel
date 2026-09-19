"""Tests for the Qolsys Panel utilities."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.qolsys_panel.utils import get_local_ip
from homeassistant.core import HomeAssistant

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


async def test_get_local_ip_takes_the_first_address(hass: HomeAssistant) -> None:
    """An adapter with several IPv4 addresses yields the first, not the last (audit L4)."""
    adapters = [
        {
            "default": True,
            "ipv4": [{"address": "192.168.1.9"}, {"address": "172.17.0.1"}],
        }
    ]
    with patch(ADAPTERS_PATH, AsyncMock(return_value=adapters)):
        assert await get_local_ip(hass) == "192.168.1.9"


async def test_get_local_ip_skips_a_default_adapter_with_no_ipv4(
    hass: HomeAssistant,
) -> None:
    """A default adapter with no IPv4 address does not shadow a later one (audit L4)."""
    adapters = [
        {"default": True, "ipv4": []},
        {"default": True, "ipv4": [{"address": "192.168.1.9"}]},
    ]
    with patch(ADAPTERS_PATH, AsyncMock(return_value=adapters)):
        assert await get_local_ip(hass) == "192.168.1.9"


async def test_get_local_ip_logs_when_there_is_nothing_to_use(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """The empty case is reported in the log (audit L4)."""
    with patch(ADAPTERS_PATH, AsyncMock(return_value=[])):
        assert await get_local_ip(hass) == ""

    assert "No default network adapter" in caplog.text
