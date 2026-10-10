"""strings.json and the English translation must not drift (review B1).

Home Assistant serves a custom integration's config-flow text from
translations/<lang>.json, so a security notice added only to strings.json is
never shown to anyone.
"""

import json
from pathlib import Path
from typing import Any

COMPONENT = Path("custom_components/qolsys_panel")


def _load(name: str) -> Any:
    return json.loads((COMPONENT / name).read_text(encoding="utf-8"))


def test_english_translation_matches_strings() -> None:
    """en.json is strings.json; any new key or wording must land in both."""
    assert _load("strings.json") == _load("translations/en.json")


def test_pairing_step_warns_about_untrusted_networks() -> None:
    """The H1 mitigation text is what the user actually sees."""
    description = _load("translations/en.json")["config"]["step"][
        "pki_autodiscovery"
    ]["description"]

    assert "network you trust" in description
