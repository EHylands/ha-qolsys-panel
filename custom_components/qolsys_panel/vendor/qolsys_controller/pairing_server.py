from __future__ import annotations

import asyncio
import logging
import random
import ssl

import aiofiles
from zeroconf._exceptions import NonUniqueNameException

from .errors import QolsysConfigError
from .mdns import QolsysMDNS
from .pki import QolsysPKI
from .settings import QolsysSettings

LOGGER = logging.getLogger(__name__)


class QolsysPairingServer:
    def __init__(
        self,
        settings: QolsysSettings,
        pki: QolsysPKI,
    ) -> None:
        self._settings = settings
        self._pki = pki
        self._mdns_server: QolsysMDNS | None = None
        self._server: asyncio.Server | None = None
        self._server_task: asyncio.Task[None] | None = None
        self._pairing_done = asyncio.Event()
        self._pairing_error: Exception | None = None
        self._pairing_port: int = 0
        self._closed = False
        self._client_active = False

    @property
    def pairing_port(self) -> int | None:
        return self._pairing_port

    async def start(self) -> None:
        if self._server is not None:
            return

        if not self._settings.check_plugin_ip():
            raise QolsysConfigError("Plugin IP Address not configured")

        # Use the configured port if set (lets the caller advertise it up front),
        # otherwise pick a random high port.
        self._pairing_port = self._settings.pairing_port or random.randint(50000, 55000)

        await self._start_mdns()
        await self._start_server()

    async def wait_until_paired(self) -> None:
        # Overall pairing deadline: fires even if no panel ever connects. Use a plain
        # loop timer (not asyncio.timeout) that records the error and sets the done
        # event, rather than cancelling this task. wait_until_paired runs inside the
        # controller's supervisor TaskGroup, and asyncio.timeout cancelling a TaskGroup
        # child does not reliably convert to TimeoutError - a raw CancelledError can
        # escape, get swallowed by run_forever, and surface as an empty/half-paired
        # result instead of a clean QolsysConfigError.
        loop = asyncio.get_running_loop()
        timeout_handle = loop.call_later(self._settings.pairing_timeout, self._on_pairing_timeout)
        try:
            await self._pairing_done.wait()
        finally:
            timeout_handle.cancel()

        if self._pairing_error is not None:
            raise self._pairing_error

    def _on_pairing_timeout(self) -> None:
        if self._pairing_done.is_set():
            return

        LOGGER.warning("Pairing Server - Timed out after %ss with no completed pairing", self._settings.pairing_timeout)
        self._pairing_error = QolsysConfigError(
            f"Pairing timed out after {self._settings.pairing_timeout} seconds - no panel completed the exchange"
        )
        self._pairing_done.set()

    async def stop(self) -> None:
        if self._closed:
            return

        self._closed = True

        if self._server_task is not None:
            self._server_task.cancel()

            try:
                await self._server_task
            except asyncio.CancelledError:
                pass

            self._server_task = None

        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        if self._mdns_server is not None:
            await self._mdns_server.stop_mdns()
            self._mdns_server = None

    async def _start_mdns(self) -> None:
        LOGGER.debug("Pairing Server - Starting mDNS Service: %s:%s", self._settings.plugin_ip, self._pairing_port)

        self._mdns_server = QolsysMDNS(
            self._settings.plugin_ip,
            self._pairing_port,
            self._settings.shared_zeroconf_instance,
        )

        try:
            await self._mdns_server.start_mdns()

        except NonUniqueNameException as err:
            raise QolsysConfigError(
                "mDNS Service Discovery Error: NonUniqueNameException - Another device on the network is using the same IP address or mDNS name"
            ) from err

        except Exception as err:
            LOGGER.exception("mDNS Service Discovery Error")
            raise QolsysConfigError(f"mDNS Service Discovery Error: {err}") from err

    async def _start_server(self) -> None:
        LOGGER.debug("Pairing Server - Starting HTTPS Server: %s:%s", self._settings.plugin_ip, self._pairing_port)

        context = await asyncio.to_thread(self._create_ssl_context)

        self._server = await asyncio.start_server(
            self.handle_client,
            self._settings.plugin_ip,
            self._pairing_port,
            ssl=context,
        )

        LOGGER.debug("Pairing Server - Press Pair Button in IQ Remote Config Page ...")

        self._server_task = asyncio.create_task(
            self._server.serve_forever(),
            name="Qolsys Pairing Server",
        )

    def _create_ssl_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)

        context.load_cert_chain(
            certfile=self._pki.cer_file_path,
            keyfile=self._pki.key_file_path,
        )

        return context

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        # Single-client guard: reject a concurrent exchange, or any connection once pairing has already completed.
        if self._client_active or self._pairing_done.is_set():
            LOGGER.warning(
                "Pairing Server - Rejecting connection from %s (pairing already in progress or completed)",
                writer.get_extra_info("peername"),
            )
            writer.close()
            await writer.wait_closed()
            return

        self._client_active = True

        received_panel_mac = False
        received_signed_client_certificate = False
        received_qolsys_cer = False

        start_token = b"-----BEGIN CERTIFICATE-----\n"
        end_token = b"-----END CERTIFICATE-----\n"

        try:
            continue_pairing = True

            while continue_pairing:
                # Receive panel MAC
                if not received_panel_mac and not received_signed_client_certificate and not received_qolsys_cer:
                    address, port = writer.get_extra_info("peername")
                    LOGGER.debug("Panel Connected from: %s:%s", address, port)

                    # Read the first 2 bytes to get the length of the incoming message (Panel MAC)
                    length = int.from_bytes(await reader.readexactly(2), "big")

                    # Panel MAC is a 17-char string (AA:BB:CC:DD:EE:FF), so the length prefix must be 17
                    if length != 17:
                        raise QolsysConfigError(f"Invalid pairing handshake from panel: expected MAC length 17, got {length}")

                    # Read Panel MAC
                    request = await reader.readexactly(length)
                    LOGGER.debug("Receiving from Panel (raw bytes): %r", request)
                    mac = request.decode()
                    self._settings.panel_mac = "".join(char for char in mac if char.isprintable())
                    self._settings.panel_ip = address
                    received_panel_mac = True

                    # Send random MAC
                    mac_bytes = self._settings.random_mac.encode()
                    message = len(mac_bytes).to_bytes(2, "big") + mac_bytes
                    LOGGER.debug("Sending to Panel (raw bytes): %r", message)

                    writer.write(message)
                    await writer.drain()

                    # Send CSR
                    async with aiofiles.open(self._pki.csr_file_path, mode="rb") as f:
                        content = await f.read()

                    LOGGER.debug("Sending to Panel: [CSR File Content]")
                    writer.write(content)
                    await writer.drain()

                    # Send separator
                    writer.write(b"sent")
                    await writer.drain()
                    continue

                # Receive signed client certificate
                if received_panel_mac and not received_signed_client_certificate and not received_qolsys_cer:
                    await reader.readuntil(start_token)

                    request = start_token + await reader.readuntil(end_token)
                    LOGGER.debug("Saving [Signed Client Certificate]")

                    async with aiofiles.open(self._pki.secure_file_path, mode="wb") as f:
                        await f.write(request)

                    received_signed_client_certificate = True

                # Receive Qolsys certificate
                if received_panel_mac and received_signed_client_certificate and not received_qolsys_cer:
                    await reader.readuntil(start_token)

                    request = start_token + await reader.readuntil(end_token)
                    LOGGER.debug("Saving [Qolsys Certificate]")

                    async with aiofiles.open(self._pki.qolsys_cer_file_path, mode="wb") as f:
                        await f.write(request)

                    received_qolsys_cer = True
                    continue_pairing = False

                    self._pairing_done.set()

        except asyncio.CancelledError:
            # Cooperative cancellation (normal shutdown) - not a pairing failure.
            LOGGER.debug("Pairing handler cancelled")
            raise

        except Exception as err:
            # Any other failure aborts pairing: record it as a QolsysConfigError so
            # wait_until_paired() re-raises it and the controller / config flow stops.
            # Not re-raised here
            LOGGER.exception("Pairing Server - Pairing failed")
            if isinstance(err, QolsysConfigError):
                self._pairing_error = err
            elif isinstance(err, TimeoutError):
                self._pairing_error = QolsysConfigError(
                    f"Pairing timed out after {self._settings.pairing_timeout} seconds - no panel completed the exchange"
                )
            else:
                self._pairing_error = QolsysConfigError(f"Pairing failed: {err!r}")
            self._pairing_done.set()

        finally:
            self._client_active = False
            writer.close()
            await writer.wait_closed()
