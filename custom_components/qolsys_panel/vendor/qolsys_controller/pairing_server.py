from __future__ import annotations

import asyncio
import logging
import random
import ssl

import aiofiles
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from zeroconf._exceptions import NonUniqueNameException

from .errors import QolsysConfigError
from .file_permissions import secure_file
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
        # Audit H1: the first peer to connect owns the pairing window; a second
        # address is refused for the rest of it.
        self._peer_address: str | None = None

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

    def _close_listener(self) -> None:
        """Stop accepting connections (audit H1).

        The listener exists only for the pairing window: it is closed the moment
        pairing completes, fails or times out, rather than staying bound until
        the controller gets around to stopping the server.
        """
        if self._server is not None and self._server.is_serving():
            LOGGER.debug("Pairing Server - Closing listening socket")
            self._server.close()

    def _on_pairing_timeout(self) -> None:
        if self._pairing_done.is_set():
            return

        self._close_listener()

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
        # Audit H1: verify_mode stays ssl.CERT_NONE. The panel presents no client
        # certificate during pairing and there is nothing to pin before pairing
        # has happened, so requiring one here would simply make pairing fail.
        # The mitigations that are possible without a panel to test against are
        # in handle_client: one peer per window, an expected-address check when
        # the panel IP is known, the peer logged, the listener bound only for the
        # window, and validation of the material the peer returns. See
        # vendor/VENDORED.md for the residual risk.
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)

        context.load_cert_chain(
            certfile=self._pki.cer_file_path,
            keyfile=self._pki.key_file_path,
        )

        return context

    def _reject(self, writer: asyncio.StreamWriter, reason: str) -> None:
        LOGGER.warning(
            "Pairing Server - Rejecting connection from %s: %s",
            writer.get_extra_info("peername"),
            reason,
        )

    async def _validate_client_certificate(self, pem: bytes) -> None:
        """Check the signed client certificate before it is stored (audit H1).

        Nothing used to check that the bytes coming back were a certificate at
        all, let alone one for the key we just sent a CSR for.
        """
        try:
            certificate = x509.load_pem_x509_certificate(pem)
        except ValueError as err:
            raise QolsysConfigError(f"Panel returned an unparsable client certificate: {err}") from err

        async with aiofiles.open(self._pki.csr_file_path, mode="rb") as f:
            csr_pem = await f.read()

        try:
            csr = x509.load_pem_x509_csr(csr_pem)
        except ValueError as err:
            raise QolsysConfigError(f"Cannot read our own CSR: {err}") from err

        def public_bytes(key: object) -> bytes:
            return key.public_bytes(  # type: ignore[attr-defined]
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )

        if public_bytes(certificate.public_key()) != public_bytes(csr.public_key()):
            raise QolsysConfigError("Panel returned a certificate for a different key")

        LOGGER.debug(
            "Pairing Server - Client certificate accepted: subject=%s issuer=%s serial=%s",
            certificate.subject.rfc4514_string(),
            certificate.issuer.rfc4514_string(),
            certificate.serial_number,
        )

    async def _validate_panel_ca(self, pem: bytes) -> None:
        """Check the CA that is about to become the pinned trust anchor (audit H1)."""
        try:
            ca = x509.load_pem_x509_certificate(pem)
        except ValueError as err:
            raise QolsysConfigError(f"Panel returned an unparsable certificate authority: {err}") from err

        LOGGER.warning(
            "Pairing Server - Pinning panel certificate authority: subject=%s issuer=%s serial=%s",
            ca.subject.rfc4514_string(),
            ca.issuer.rfc4514_string(),
            ca.serial_number,
        )

        async with aiofiles.open(self._pki.secure_file_path, mode="rb") as f:
            client_pem = await f.read()

        try:
            x509.load_pem_x509_certificate(client_pem).verify_directly_issued_by(ca)
        except Exception as err:  # noqa: BLE001 - evidence only, see below
            # Not fatal: a panel that signs through an intermediate would fail
            # this check, and breaking pairing on it cannot be tested without a
            # panel. Logged so a mismatch is at least visible.
            LOGGER.warning(
                "Pairing Server - The signed client certificate does not verify against the certificate authority the panel sent: %s",
                err,
            )

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peername = writer.get_extra_info("peername")
        peer_address = peername[0] if peername else None

        # Single-client guard: reject a concurrent exchange, or any connection once pairing has already completed.
        if self._client_active or self._pairing_done.is_set():
            self._reject(writer, "pairing already in progress or completed")
            writer.close()
            await writer.wait_closed()
            return

        # Audit H1: when the panel address is known (re-pairing an existing
        # install), only that address may pair.
        expected = self._settings.panel_ip
        if expected and peer_address != expected:
            self._reject(writer, f"expected the panel at {expected}")
            writer.close()
            await writer.wait_closed()
            return

        # Audit H1: the first peer of the window owns it. A retry from the same
        # panel is still allowed; a second device is not.
        if self._peer_address is not None and peer_address != self._peer_address:
            self._reject(writer, f"pairing window already belongs to {self._peer_address}")
            writer.close()
            await writer.wait_closed()
            return

        self._peer_address = peer_address
        LOGGER.warning("Pairing Server - Pairing with %s - confirm this is your panel", peername)

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

                    # Audit H1: check what came back before trusting it.
                    await self._validate_client_certificate(request)

                    LOGGER.debug("Saving [Signed Client Certificate]")

                    async with aiofiles.open(self._pki.secure_file_path, mode="wb") as f:
                        await f.write(request)

                    # Audit H2: the signed client certificate authenticates as the
                    # keypad; it must not be world readable.
                    await secure_file(self._pki.secure_file_path)

                    received_signed_client_certificate = True

                # Receive Qolsys certificate
                if received_panel_mac and received_signed_client_certificate and not received_qolsys_cer:
                    await reader.readuntil(start_token)

                    request = start_token + await reader.readuntil(end_token)

                    # Audit H1: this file becomes the pinned trust anchor.
                    await self._validate_panel_ca(request)

                    LOGGER.debug("Saving [Qolsys Certificate]")

                    async with aiofiles.open(self._pki.qolsys_cer_file_path, mode="wb") as f:
                        await f.write(request)

                    await secure_file(self._pki.qolsys_cer_file_path)

                    received_qolsys_cer = True
                    continue_pairing = False

                    self._close_listener()
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

            self._close_listener()
            self._pairing_done.set()

        finally:
            self._client_active = False
            writer.close()
            await writer.wait_closed()
