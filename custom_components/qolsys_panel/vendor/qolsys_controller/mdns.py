import socket

from zeroconf import ServiceInfo
from zeroconf.asyncio import AsyncZeroconf


class QolsysMDNS:
    def __init__(self, ip: str, port: int, external_zero_conf: AsyncZeroconf | None = None) -> None:
        self._is_running_own_instance = False

        # Add possible external zeroconf instance provided by Home Assistant by example
        # If no external instance is provided, create our own
        if external_zero_conf:
            self.azc = external_zero_conf
        else:
            self.azc = AsyncZeroconf()
            self._is_running_own_instance = True

        self.mdns_info = ServiceInfo(
            "_http._tcp.local.",
            "NsdPairService._http._tcp.local.",
            addresses=[socket.inet_aton(ip)],
            port=port,
        )

    async def start_mdns(self) -> None:
        await self.azc.async_register_service(self.mdns_info)

    async def stop_mdns(self) -> None:
        await self.azc.async_unregister_service(self.mdns_info)
        if self._is_running_own_instance:
            await self.azc.async_close()
