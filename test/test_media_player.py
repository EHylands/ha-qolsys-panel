"""Tests for the Qolsys Panel media player."""

from unittest.mock import MagicMock

from conftest import PANEL_MAC
import pytest

from custom_components.qolsys_panel.media_player import (
    Qolsys_MediaPlayer,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant

UID = PANEL_MAC


@pytest.fixture
def controller() -> MagicMock:
    """A controller mock with an awaitable speak command."""
    from unittest.mock import AsyncMock

    c = MagicMock()
    c.commands.panel.speak = AsyncMock()
    return c


async def test_async_setup_entry_creates_entities(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup builds a single TTS media player."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], Qolsys_MediaPlayer)


@pytest.mark.parametrize("media_type", ["tts", "text"])
async def test_play_media_speaks(
    hass: HomeAssistant, controller: MagicMock, media_type: str
) -> None:
    """A text/tts message is spoken by the panel."""
    player = Qolsys_MediaPlayer(hass, controller, UID)
    await player.async_play_media(media_type, "hello")
    controller.commands.panel.speak.assert_awaited_once_with("hello")


async def test_play_media_rejects_non_text_type(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """A non-text media type is rejected without speaking."""
    player = Qolsys_MediaPlayer(hass, controller, UID)
    await player.async_play_media("music", "hello")
    controller.commands.panel.speak.assert_not_awaited()


async def test_play_media_rejects_non_string_id(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """A non-string media id is rejected without speaking."""
    player = Qolsys_MediaPlayer(hass, controller, UID)
    await player.async_play_media("tts", 12345)
    controller.commands.panel.speak.assert_not_awaited()
