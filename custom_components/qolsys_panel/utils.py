"""Utility functions for Qolsys Panel Integration."""

import logging

from homeassistant.components import network
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def get_local_ip(hass: HomeAssistant) -> str:
    """Return the IPv4 address the panel should call back on.

    Audit L4: this used to keep overwriting the address across every IPv4 of
    every default adapter, so on an adapter with several addresses the panel was
    told to call back on whichever happened to come last, and a machine with no
    default adapter returned "" with nothing in the log.
    """
    for adapter in await network.async_get_adapters(hass):
        if adapter["default"] and adapter["ipv4"]:
            return str(adapter["ipv4"][0]["address"])

    _LOGGER.warning("No default network adapter with an IPv4 address; cannot pair")
    return ""
