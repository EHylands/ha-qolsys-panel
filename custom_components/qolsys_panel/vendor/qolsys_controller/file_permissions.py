"""Restrictive file modes for secret material.

Added while vendoring (audit H2 and H3). Every PKI artifact and the user-code
file used to be written through ``aiofiles.open(path, "wb")``, which creates
with 0o666 masked by the process umask - 0o644 on HAOS. That put an
unencrypted RSA private key, the signed client certificate that authenticates
as the keypad, and the alarm user codes into a world-readable path under
/config, which every add-on can read and which is included in every Home
Assistant backup.
"""

from __future__ import annotations

import asyncio
import logging
import stat
from pathlib import Path

LOGGER = logging.getLogger(__name__)

# Owner read/write only, and owner-traversable directories.
SECRET_FILE_MODE = 0o600
SECRET_DIR_MODE = 0o700


def set_mode(path: Path, mode: int) -> None:
    """Set path to mode, quietly doing nothing if it is already correct.

    Never follows a symlink (review N1): stat() and chmod() both resolve links,
    so a link planted in the PKI directory would otherwise have its target
    chmodded anywhere the Home Assistant user can write.
    """
    try:
        if path.is_symlink():
            LOGGER.warning("Refusing to change permissions through a symlink: %s", path)
            return
        if stat.S_IMODE(path.stat().st_mode) == mode:
            return
        path.chmod(mode)
        LOGGER.debug("Restricted permissions on %s to %s", path, oct(mode))
    except FileNotFoundError:
        LOGGER.debug("Cannot restrict permissions, file not found: %s", path)
    except OSError as err:
        # A filesystem that cannot represent the mode (a mounted share, say) must
        # not break pairing or startup; the operator needs to know, though.
        LOGGER.warning("Could not restrict permissions on %s: %s", path, err)


def secure_file_sync(path: Path) -> None:
    """Make a file owner-only from synchronous (executor) code."""
    set_mode(path, SECRET_FILE_MODE)


async def secure_file(path: Path) -> None:
    """Make a file readable and writable by its owner only."""
    await asyncio.to_thread(set_mode, path, SECRET_FILE_MODE)


async def secure_directory(path: Path) -> None:
    """Make a directory accessible by its owner only."""
    await asyncio.to_thread(set_mode, path, SECRET_DIR_MODE)


def secure_tree(root: Path) -> None:
    """Repair the modes of an existing tree of secret material.

    Installations created before this fix carry 0o755 directories and 0o644
    keys; a one-time pass on startup fixes them instead of only protecting new
    pairings.
    """
    if root.is_symlink() or not root.is_dir():
        return

    set_mode(root, SECRET_DIR_MODE)
    for entry in root.rglob("*"):
        # rglob does not descend into a symlinked directory but does yield the
        # link itself; set_mode refuses it, and skipping here keeps the log to
        # one line per link (review N1).
        if entry.is_symlink():
            LOGGER.warning("Skipping symlink in the PKI directory: %s", entry)
            continue
        if entry.is_dir():
            set_mode(entry, SECRET_DIR_MODE)
        elif entry.is_file():
            set_mode(entry, SECRET_FILE_MODE)
