"""Utility functions for Qolsys Panel integration."""
from homeassistant.components import network
from homeassistant.core import HomeAssistant


async def get_local_ip(hass: HomeAssistant) -> str:
    """Get Home Assistant ocal IP address."""
    local_ip = ''
    adapters = await network.async_get_adapters(hass)
    for adapter in adapters:
        if adapter["default"]:
            for ip_info in adapter["ipv4"]:
                local_ip = ip_info["address"]

    return local_ip
