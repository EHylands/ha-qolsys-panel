import logging

from qolsys_controller import qolsys_controller

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.const import STATE_IDLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysPanelEntity
from .types import QolsysPanelConfigEntry


_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up media players."""
    entities: list[MediaPlayerEntity] = []
    QolsysPanel = config_entry.runtime_data

    # Add Doorbell Binary Sensor
    entities.append(Qolsys_MediaPlayer(hass, QolsysPanel, config_entry.unique_id))

class Qolsys_MediaPlayer(QolsysPanelEntity,MediaPlayerEntity):
    """Qolsys TTS-only media player."""

    _attr_name = "Qolsys Media Player"
    _attr_supported_features = MediaPlayerEntityFeature.PLAY_MEDIA
    _attr_state = STATE_IDLE

    def __init__(self, hass, QolsysPanel: qolsys_controller, unique_id: str):
        super().__init__(QolsysPanel, unique_id)
        self.hass = hass
        self._attr_unique_id = f"{unique_id}_panel_media_payer"

    async def async_play_media(self, media_type, media_id, **kwargs):
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

        await self.QolsysPanel.command_panel_speak(media_id)
