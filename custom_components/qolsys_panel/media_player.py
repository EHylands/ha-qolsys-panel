import logging
from typing import Any

from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerState
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysPanelEntity
from .types import QolsysPanelConfigEntry
from .vendor.qolsys_controller import qolsys_controller

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up media players."""
    entities: list[MediaPlayerEntity] = []
    QolsysPanel = config_entry.runtime_data
    if (unique_id := config_entry.unique_id) is None:
        # A forwarded platform must not raise ConfigEntryNotReady: HA logs a
        # complaint rather than retrying, and __init__.async_setup_entry already
        # refuses a None unique_id before any platform is set up (review N5).
        raise ValueError("Config entry has no unique_id; re-add the integration")

    # Add Doorbell Binary Sensor
    entities.append(Qolsys_MediaPlayer(hass, QolsysPanel, unique_id))

    async_add_entities(entities)


class Qolsys_MediaPlayer(QolsysPanelEntity, MediaPlayerEntity):
    """Qolsys TTS-only media player."""

    _attr_name = "Qolsys TTS Player"
    _attr_supported_features = MediaPlayerEntityFeature.PLAY_MEDIA
    _attr_state = MediaPlayerState.IDLE

    def __init__(
        self, hass: HomeAssistant, QolsysPanel: qolsys_controller, unique_id: str
    ) -> None:
        super().__init__(QolsysPanel, unique_id)
        self.hass = hass
        self._attr_unique_id = f"{unique_id}_panel_media_player"

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Accept only text-based messages."""

        # Only accept TTS/text media types
        if media_type not in ("tts", "text"):
            _LOGGER.warning(
                "Rejected media type '%s'. This player only accepts text.", media_type
            )
            return

        # Ensure the message is actually a string
        if not isinstance(media_id, str):
            _LOGGER.warning("Rejected media_id because it is not a string")
            return

        await self.QolsysPanel.commands.panel.speak(media_id)
