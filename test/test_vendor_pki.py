"""Tests for the vendored PKI file permissions (audit H2, L6 item 3)."""

from pathlib import Path
import stat
from unittest.mock import MagicMock

import pytest

from custom_components.qolsys_panel.vendor.qolsys_controller.file_permissions import (
    SECRET_DIR_MODE,
    SECRET_FILE_MODE,
    secure_tree,
)
from custom_components.qolsys_panel.vendor.qolsys_controller.pki import QolsysPKI

PKI_ID = "aa:bb:cc:dd:ee:ff"


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture
def pki(tmp_path: Path) -> QolsysPKI:
    """A PKI rooted in a temporary config directory."""
    settings = MagicMock()
    settings.pki_directory = tmp_path / "pki"
    settings.mqtt_bridge_directory = tmp_path / "mqtt_bridge"
    settings.pki_directory.mkdir()
    settings.mqtt_bridge_directory.mkdir()
    return QolsysPKI(settings)


async def test_created_key_material_is_owner_only(pki: QolsysPKI) -> None:
    """A fresh pairing writes the key, cert and CSR 0600 in a 0700 directory."""
    assert await pki.create(PKI_ID, 1024) is True

    assert _mode(pki.key_file_path.parent) == SECRET_DIR_MODE
    for path in (pki.key_file_path, pki.cer_file_path, pki.csr_file_path):
        assert _mode(path) == SECRET_FILE_MODE, path


async def test_existing_material_is_repaired_on_startup(pki: QolsysPKI) -> None:
    """An install paired before the fix gets its 0644 key mode repaired."""
    assert await pki.create(PKI_ID, 1024) is True

    # Put the tree back the way older versions left it.
    pki.key_file_path.parent.chmod(0o755)
    pki.key_file_path.chmod(0o644)
    pki.cer_file_path.chmod(0o644)

    await pki.secure_existing_material()

    assert _mode(pki.key_file_path.parent) == SECRET_DIR_MODE
    assert _mode(pki.key_file_path) == SECRET_FILE_MODE
    assert _mode(pki.cer_file_path) == SECRET_FILE_MODE


def test_secure_tree_ignores_a_missing_directory(tmp_path: Path) -> None:
    """The repair pass is a no-op when nothing has been paired yet."""
    secure_tree(tmp_path / "does-not-exist")
