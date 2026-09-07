"""Tests for the vendored pairing server (audit H1, L6 item 3)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import pytest

from custom_components.qolsys_panel.vendor.qolsys_controller.errors import (
    QolsysConfigError,
)
from custom_components.qolsys_panel.vendor.qolsys_controller.pairing_server import (
    QolsysPairingServer,
)
from custom_components.qolsys_panel.vendor.qolsys_controller.pki import QolsysPKI

PKI_ID = "aa:bb:cc:dd:ee:ff"
PANEL_IP = "192.168.1.50"


def _sign(public_key, issuer_name: str) -> bytes:
    """Sign a certificate for public_key, the way a panel would."""
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_name)])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .sign(ca_key, hashes.SHA256())
    )
    return certificate.public_bytes(encoding=serialization.Encoding.PEM)


@pytest.fixture
async def paired(tmp_path: Path) -> tuple[QolsysPairingServer, MagicMock, QolsysPKI]:
    """A pairing server with our own key and CSR already on disk."""
    settings = MagicMock()
    settings.pki_directory = tmp_path / "pki"
    settings.mqtt_bridge_directory = tmp_path / "mqtt_bridge"
    settings.pki_directory.mkdir()
    settings.mqtt_bridge_directory.mkdir()
    settings.panel_ip = ""
    pki = QolsysPKI(settings)
    assert await pki.create(PKI_ID, 1024) is True
    return QolsysPairingServer(settings, pki), settings, pki


def _writer(address: str) -> MagicMock:
    writer = MagicMock()
    writer.get_extra_info.return_value = (address, 51000)
    writer.wait_closed = AsyncMock()
    return writer


async def test_certificate_for_our_key_is_accepted(paired) -> None:
    """A certificate signed for the key in our CSR passes validation."""
    server, _settings, pki = paired
    our_key = serialization.load_pem_private_key(
        pki.key_file_path.read_bytes(), password=None
    )

    await server._validate_client_certificate(_sign(our_key.public_key(), "panel"))


async def test_certificate_for_another_key_is_rejected(paired) -> None:
    """A certificate for someone else's key never becomes our identity."""
    server, _settings, _pki = paired
    other = rsa.generate_private_key(public_exponent=65537, key_size=1024)

    with pytest.raises(QolsysConfigError):
        await server._validate_client_certificate(_sign(other.public_key(), "panel"))


async def test_garbage_certificate_is_rejected(paired) -> None:
    """Bytes that are not a certificate are refused before being written."""
    server, _settings, _pki = paired

    with pytest.raises(QolsysConfigError):
        await server._validate_client_certificate(b"-----BEGIN CERTIFICATE-----\nnope\n")


async def test_garbage_certificate_authority_is_rejected(paired) -> None:
    """The pinned trust anchor must at least parse as X.509."""
    server, _settings, _pki = paired

    with pytest.raises(QolsysConfigError):
        await server._validate_panel_ca(b"not a certificate")


async def test_connection_from_another_address_is_rejected(paired) -> None:
    """With the panel IP known, only the panel may pair (audit H1)."""
    server, settings, _pki = paired
    settings.panel_ip = PANEL_IP
    reader, writer = MagicMock(), _writer("192.168.1.99")

    await server.handle_client(reader, writer)

    reader.readexactly.assert_not_called()
    writer.close.assert_called_once()


async def test_second_peer_cannot_take_over_the_window(paired) -> None:
    """The first peer owns the pairing window (audit H1)."""
    server, _settings, _pki = paired
    server._peer_address = "192.168.1.50"
    reader, writer = MagicMock(), _writer("192.168.1.99")

    await server.handle_client(reader, writer)

    reader.readexactly.assert_not_called()
    writer.close.assert_called_once()


async def test_connection_after_pairing_is_rejected(paired) -> None:
    """Once pairing is done the server pairs with nobody else."""
    server, _settings, _pki = paired
    server._pairing_done.set()
    reader, writer = MagicMock(), _writer(PANEL_IP)

    await server.handle_client(reader, writer)

    reader.readexactly.assert_not_called()
    writer.close.assert_called_once()


async def test_timeout_closes_the_listening_socket(paired) -> None:
    """The listener is bound for the pairing window only (audit H1)."""
    server, settings, _pki = paired
    settings.pairing_timeout = 0.01

    # Stand in for asyncio.Server: the test harness forbids real sockets.
    listening = MagicMock()
    listening.is_serving.return_value = True
    server._server = listening

    with pytest.raises(QolsysConfigError):
        await server.wait_until_paired()

    listening.close.assert_called_once()
