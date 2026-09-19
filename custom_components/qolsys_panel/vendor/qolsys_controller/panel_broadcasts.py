"""Messages the panel sends to every keypad on its own, not in reply to anything.

They arrive on the same response topic as command replies but carry no requestID.
The ones the library has no use for are skipped quietly; a type never seen before
is logged once, by name, so a panel update that starts sending something new is
noticed without becoming daily noise. Same pattern as the unused database tables.
"""

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)

# Broadcast event names known to carry nothing this library uses.
#   splitMessage: the panel's weather forecast and other keypad display text,
#                 hex-encoded, sent daily (seen 2026-09-07).
IGNORED_BROADCASTS = frozenset({"splitMessage"})


class QolsysPanelBroadcasts:
    def __init__(self) -> None:
        self._warned: set[str] = set()

    def handle(self, message: dict[str, Any]) -> None:
        event = str(message.get("eventName") or message.get("event") or "?")
        if event in IGNORED_BROADCASTS:
            LOGGER.debug("Panel broadcast %s ignored (%d bytes)", event, len(str(message)))
            return
        if event not in self._warned:
            self._warned.add(event)
            LOGGER.warning(
                "Panel broadcast of a type this library does not know: %s (keys: %s); "
                "add it to IGNORED_BROADCASTS if it can be ignored. Logged once per type.",
                event,
                ", ".join(sorted(str(k) for k in message)),
            )
        else:
            LOGGER.debug("Panel broadcast %s (already reported)", event)
