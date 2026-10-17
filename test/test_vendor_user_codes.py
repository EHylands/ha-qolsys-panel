"""Tests for hashed user codes in the vendored library (audit H3, L5, L6)."""

import json
from pathlib import Path
import stat
from unittest.mock import MagicMock

import pytest

from custom_components.qolsys_panel.vendor.qolsys_controller.errors import (
    QolsysConfigError,
)
from custom_components.qolsys_panel.vendor.qolsys_controller.panel import QolsysPanel
from custom_components.qolsys_panel.vendor.qolsys_controller.user_codes import (
    hash_user_code,
    is_hash,
    verify_user_code,
)

# A cheap iteration count: these tests check the format and the plumbing, not
# the cost factor.
FAST = 10


def _panel(tmp_path: Path, users: list[object]) -> QolsysPanel:
    """A panel whose users.conf holds the given rows."""
    path = tmp_path / "users.conf"
    path.write_text(json.dumps(users), encoding="utf-8")
    controller = MagicMock()
    controller.settings.users_file_path = path
    return QolsysPanel(controller)


def test_hash_round_trip() -> None:
    """A hashed code verifies, a different code does not."""
    stored = hash_user_code("1234", iterations=FAST)

    assert is_hash(stored)
    assert "1234" not in stored
    assert verify_user_code("1234", stored) is True
    assert verify_user_code("1235", stored) is False
    assert verify_user_code("", stored) is False


def test_hash_is_salted() -> None:
    """The same code hashes differently each time."""
    assert hash_user_code("1234", iterations=FAST) != hash_user_code(
        "1234", iterations=FAST
    )


@pytest.mark.parametrize(
    "stored", ["", "1234", "pbkdf2_sha256$notanint$c2FsdA==$aGFzaA==", "sha1$1$a$b"]
)
def test_verify_rejects_garbage(stored: str) -> None:
    """A malformed or non-hash stored value never verifies."""
    assert verify_user_code("1234", stored) is False


def test_check_user_matches_the_hash(tmp_path: Path) -> None:
    """check_user returns the id behind a stored hash, and -1 otherwise."""
    panel = _panel(
        tmp_path,
        [
            {"id": 1, "user_code_hash": hash_user_code("1111", iterations=FAST)},
            {"id": 7, "user_code_hash": hash_user_code("2222", iterations=FAST)},
        ],
    )
    panel.read_users_file()

    assert panel.check_user("2222") == 7
    assert panel.check_user("9999") == -1
    assert panel.check_user("") == -1


def test_cleartext_codes_are_hashed_and_rewritten(tmp_path: Path) -> None:
    """A hand-written cleartext users.conf is hashed in place, 0600 (audit H3)."""
    panel = _panel(tmp_path, [{"id": 3, "user_code": "4321"}])
    path = tmp_path / "users.conf"
    path.chmod(0o644)

    panel.read_users_file()

    written = json.loads(path.read_text(encoding="utf-8"))
    assert written[0]["id"] == 3
    assert "user_code" not in written[0]
    assert is_hash(written[0]["user_code_hash"])
    assert "4321" not in path.read_text(encoding="utf-8")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert panel.check_user("4321") == 3


def test_missing_users_file_is_not_an_error(tmp_path: Path) -> None:
    """No users.conf simply means no codes are configured."""
    controller = MagicMock()
    controller.settings.users_file_path = tmp_path / "users.conf"
    panel = QolsysPanel(controller)

    panel.read_users_file()

    assert panel.check_user("1234") == -1


@pytest.mark.parametrize(
    "rows",
    [
        [{"user_code": "1234"}],  # no id
        [{"id": "3", "user_code": "1234"}],  # id is not an int
        [{"id": 3}],  # neither a code nor a hash
        [{"id": 3, "user_code": None}],  # the None that used to match a None lookup
        ["nonsense"],
    ],
)
def test_malformed_entries_are_ignored(tmp_path: Path, rows: list[object]) -> None:
    """A malformed row is dropped and counted, not raised (audit H3, review N4)."""
    panel = _panel(tmp_path, rows)

    panel.read_users_file()

    assert panel.users == []
    assert panel.users_file_malformed_rows == 1
    assert panel.check_user("1234") == -1


def test_invalid_json_is_rejected(tmp_path: Path) -> None:
    """A broken users.conf raises a configuration error."""
    path = tmp_path / "users.conf"
    path.write_text("{not json", encoding="utf-8")
    controller = MagicMock()
    controller.settings.users_file_path = path

    with pytest.raises(QolsysConfigError):
        QolsysPanel(controller).read_users_file()


def test_one_bad_row_does_not_lose_the_good_ones(tmp_path: Path) -> None:
    """A typo in one entry must not take the integration offline (review N4)."""
    panel = _panel(
        tmp_path,
        [
            {"id": "oops", "user_code": "1111"},
            {"id": 2, "user_code_hash": hash_user_code("2222", iterations=FAST)},
        ],
    )

    panel.read_users_file()

    assert panel.check_user("2222") == 2
    assert panel.users_file_malformed_rows == 1


def test_a_file_with_a_bad_row_is_not_rewritten(tmp_path: Path) -> None:
    """Rewriting would drop the line the operator has to fix (review N4)."""
    panel = _panel(
        tmp_path,
        [{"id": "oops", "user_code": "1111"}, {"id": 2, "user_code": "2222"}],
    )
    path = tmp_path / "users.conf"

    panel.read_users_file()

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk[0] == {"id": "oops", "user_code": "1111"}
    assert panel.check_user("2222") == 2
