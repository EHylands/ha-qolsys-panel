"""Hashing and constant-time verification of alarm user codes.

Added while vendoring (audit H3 and L5). users.conf used to hold the family's
real panel codes in cleartext next to the keypad private key, at 0o644 and
inside every Home Assistant backup, and check_user compared them with ``==``,
which short-circuits on the first differing character.

Codes are stored as PBKDF2-HMAC-SHA256 with a per-code random salt, in a
self-describing string so the parameters can be raised later without breaking
existing files:

    pbkdf2_sha256$<iterations>$<salt base64>$<hash base64>

A 4-digit code only has 10,000 possibilities, so the KDF does not make a stolen
file unbreakable; it removes the cleartext, costs an attacker real time per
guess, and makes the comparison constant-time.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 210000
SALT_BYTES = 16
_HASH_NAME = "sha256"


def _derive(user_code: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac(_HASH_NAME, user_code.encode(), salt, iterations)


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def hash_user_code(user_code: str, iterations: int = ITERATIONS) -> str:
    """Return a storable hash of a user code."""
    salt = secrets.token_bytes(SALT_BYTES)
    derived = _derive(user_code, salt, iterations)
    return f"{ALGORITHM}${iterations}${_b64(salt)}${_b64(derived)}"


def is_hash(value: str) -> bool:
    """Return True if value looks like a stored hash rather than a code."""
    return value.startswith(f"{ALGORITHM}$")


def verify_user_code(user_code: str, stored: str) -> bool:
    """Check a code against a stored hash in constant time."""
    if not user_code or not stored:
        return False

    try:
        algorithm, iterations, salt, expected = stored.split("$")
        if algorithm != ALGORITHM:
            return False
        derived = _derive(user_code, base64.b64decode(salt), int(iterations))
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(_b64(derived), expected)
