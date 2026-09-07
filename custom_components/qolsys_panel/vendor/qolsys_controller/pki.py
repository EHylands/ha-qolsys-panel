import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiofiles
import aiofiles.os
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from .settings import QolsysSettings

LOGGER = logging.getLogger(__name__)


class QolsysPKI:
    def __init__(self, settings: QolsysSettings) -> None:
        self._id = ""
        self._subkeys_directory: Path = Path()
        self._key: Path = Path()
        self._cer: Path = Path()
        self._csr: Path = Path()
        self._secure: Path = Path()
        self._qolsys: Path = Path()

        self._settings = settings

    @property
    def id(self) -> str:
        return self._id

    def formatted_id(self) -> str:
        return ":".join(self.id[i : i + 2] for i in range(0, len(self.id), 2))

    def set_id(self, pki_id: str) -> None:
        self._id = pki_id.replace(":", "").lower()

        if self.id != "":
            LOGGER.debug("Using PKI: %s", self.formatted_id())
            self._subkeys_directory = self._settings.pki_directory.joinpath(Path(self.id))
        else:
            LOGGER.debug("No PKI ID configured")

    @property
    def key(self) -> Path:
        return self._key

    @property
    def cer(self) -> Path:
        return self._cer

    @property
    def csr(self) -> Path:
        return self._csr

    @property
    def secure(self) -> Path:
        return self._secure

    @property
    def qolsys(self) -> Path:
        return self._qolsys

    async def pairing_resume_pki_set(self, in_progress: bool) -> None:
        if self.id == "":
            LOGGER.debug("No PKI ID configured to mark pairing resume progress")
            return

        progress_file = self._settings.pairing_progress_file
        progress_path = self._subkeys_directory.joinpath(progress_file)

        if in_progress:
            try:
                async with aiofiles.open(progress_path, "x"):
                    pass
            except FileExistsError:
                pass
        else:
            try:
                await aiofiles.os.remove(progress_path)
            except FileNotFoundError:
                pass

        LOGGER.debug("PKI folder - %s - In Progress: %s", self.id, in_progress)

    async def pairing_resume_get_in_progress_pki(self) -> str | None:
        pattern = r"^[A-Fa-f0-9]{12}$"
        LOGGER.debug("Resume Pairing Process Enabled")

        def scan() -> str | None:
            with os.scandir(self._settings.pki_directory) as entries:
                for entry in entries:
                    if entry.is_dir() and re.fullmatch(pattern, entry.name):
                        in_progress = (Path(entry.path) / self._settings.pairing_progress_file).exists()
                        LOGGER.debug(
                            "PKI folder - %s - In Progress: %s",
                            entry.name,
                            in_progress,
                        )
                        if in_progress:
                            return entry.name
                LOGGER.debug("No PKI folder found to resume pairing process")
                return None

        return await asyncio.to_thread(scan)

    def auto_discover_pki(self) -> bool:
        pattern = r"^[A-Fa-f0-9]{12}$"

        LOGGER.debug("Auto Discovery Enabled")
        with os.scandir(self._settings.pki_directory) as entries:
            for entry in entries:
                if entry.is_dir() and re.fullmatch(pattern, entry.name):
                    self.set_id(entry.name)
                    return True

        return False

    async def check_key_file(self) -> bool:
        if await asyncio.to_thread(self.key_file_path.exists):
            LOGGER.debug("Found KEY")
            return True
        LOGGER.debug("No KEY File")
        return False

    async def check_cer_file(self) -> bool:
        if await asyncio.to_thread(self.cer_file_path.exists):
            LOGGER.debug("Found CER")
            return True
        LOGGER.debug("No CER File")
        return False

    async def check_csr_file(self) -> bool:
        if await asyncio.to_thread(self.csr_file_path.exists):
            LOGGER.debug("Found CSR")
            return True
        LOGGER.debug("No CSR File")
        return False

    async def check_secure_file(self) -> bool:
        if await asyncio.to_thread(self.secure_file_path.exists):
            LOGGER.debug("Found Signed Client Certificate")
            return True
        LOGGER.debug("No Signed Client Certificate File")
        return False

    async def check_qolsys_cer_file(self) -> bool:
        if await asyncio.to_thread(self.qolsys_cer_file_path.exists):
            LOGGER.debug("Found Qolsys Certificate")
            return True
        LOGGER.debug("No Qolsys Certificate File")
        return False

    async def check_mqtt_bridge_cer_file(self) -> bool:
        if await asyncio.to_thread(self.mqtt_bridge_cer_file_path.exists):
            LOGGER.debug("MQTT Brige Broker: Found CER")
            return True
        LOGGER.debug("MQTT Brige Broker: No CER File")
        return False

    async def check_mqtt_bridge_key_file(self) -> bool:
        if await asyncio.to_thread(self.mqtt_bridge_key_file_path.exists):
            LOGGER.debug("MQTT Brige Broker: Found KEY")
            return True
        LOGGER.debug("MQTT Brige Broker: No KEY File")
        return False

    @property
    def key_file_path(self) -> Path:
        return self._subkeys_directory.joinpath(self.id + ".key")

    @property
    def csr_file_path(self) -> Path:
        return self._subkeys_directory.joinpath(self.id + ".csr")

    @property
    def cer_file_path(self) -> Path:
        return self._subkeys_directory.joinpath(self.id + ".cer")

    @property
    def secure_file_path(self) -> Path:
        return self._subkeys_directory.joinpath(self.id + ".secure")

    @property
    def qolsys_cer_file_path(self) -> Path:
        return self._subkeys_directory.joinpath(self.id + ".qolsys")

    @property
    def mqtt_bridge_cer_file_path(self) -> Path:
        return self._settings.mqtt_bridge_directory.joinpath(self._settings._mqtt_bridge_cerfile)

    @property
    def mqtt_bridge_key_file_path(self) -> Path:
        return self._settings.mqtt_bridge_directory.joinpath(self._settings._mqtt_bridge_keyfile)

    async def create_mqtt_bridge_certificates(self) -> bool:
        # Check for MQTT Bridge Broker certificate and key file collision
        if await self.check_mqtt_bridge_cer_file() or await self.check_mqtt_bridge_key_file():
            LOGGER.error("MQTT Bridge Broker: Certificate or Key File Collision")
            return False

        LOGGER.debug("MQTT Bridge Broker: Creating KEY")
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=self._settings.key_size)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        async with aiofiles.open(self.mqtt_bridge_key_file_path, "wb") as f:
            await f.write(private_pem)

        LOGGER.debug("MQTT Bridge Broker: Creating CER")
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "US"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "US"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Qolsys Controller"),
                x509.NameAttribute(NameOID.COMMON_NAME, "MQTT Bridge Broker"),
            ]
        )
        cert = (
            x509.CertificateBuilder()
            .subject_name(
                subject,
            )
            .issuer_name(
                issuer,
            )
            .public_key(
                private_key.public_key(),
            )
            .serial_number(
                x509.random_serial_number(),
            )
            .not_valid_before(
                datetime.now(timezone.utc),  # noqa: UP017
            )
            .not_valid_after(
                datetime.now(timezone.utc) + timedelta(days=3650),  # noqa: UP017
            )
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .sign(private_key, hashes.SHA256())
        )
        cert_pem = cert.public_bytes(encoding=serialization.Encoding.PEM)

        async with aiofiles.open(self.mqtt_bridge_cer_file_path, "wb") as f:
            await f.write(cert_pem)

        return True

    async def create(self, mac: str, key_size: int) -> bool:
        self.set_id(mac)

        # Check if directory exist
        if await asyncio.to_thread(self._subkeys_directory.resolve().exists):
            LOGGER.error("Create Directory Collision")
            return False

        # Check for private key collision
        if await self.check_key_file():
            LOGGER.error("Create KEY File Collision")
            return False

        # Check for CER file collision
        if await self.check_cer_file():
            LOGGER.error("Create CER File Collision")
            return False

        # Check for CSR file collision
        if await self.check_csr_file():
            LOGGER.error("Create CSR File Collision")
            return False

        # Check for Signed Certificate file collision
        if await self.check_secure_file():
            LOGGER.error("Create Signed Certificate File Collision")
            return False

        LOGGER.debug("Creating PKI: %s", self.formatted_id())
        LOGGER.debug("Creating PKI Directory")
        await asyncio.to_thread(self._subkeys_directory.resolve().mkdir, parents=True, exist_ok=True)

        LOGGER.debug("Creating KEY")
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        path = self._subkeys_directory.joinpath(self.id + ".key")
        async with aiofiles.open(path, "wb") as f:
            await f.write(private_pem)

        LOGGER.debug("Creating CER")
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "SanJose"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, ""),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Qolsys Inc."),
                x509.NameAttribute(NameOID.COMMON_NAME, "www.qolsys.com "),
            ]
        )
        cert = (
            x509.CertificateBuilder()
            .subject_name(
                subject,
            )
            .issuer_name(
                issuer,
            )
            .public_key(
                private_key.public_key(),
            )
            .serial_number(
                x509.random_serial_number(),
            )
            .not_valid_before(
                datetime.now(timezone.utc),  # noqa: UP017
            )
            .not_valid_after(
                datetime.now(timezone.utc) + timedelta(days=3650),  # noqa: UP017
            )
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .sign(private_key, hashes.SHA256())
        )
        cert_pem = cert.public_bytes(encoding=serialization.Encoding.PEM)

        path = self._subkeys_directory.joinpath(self.id + ".cer")
        async with aiofiles.open(path, "wb") as f:
            await f.write(cert_pem)

        LOGGER.debug("Creating CSR")
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(
                subject,
            )
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .sign(private_key, hashes.SHA256())
        )

        # Save CSR to file
        csr_pem = csr.public_bytes(encoding=serialization.Encoding.PEM)
        path = self._subkeys_directory.joinpath(self.id + ".csr")
        async with aiofiles.open(path, "wb") as f:
            await f.write(csr_pem)

        return True
