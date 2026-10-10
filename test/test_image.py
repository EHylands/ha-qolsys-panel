"""Tests for the Qolsys Panel peek-in image entity."""

from unittest.mock import MagicMock

from conftest import PANEL_MAC
import pytest

from custom_components.qolsys_panel.image import QolsysPicture_PeekIn, async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

UID = PANEL_MAC


@pytest.fixture
def controller() -> MagicMock:
    """A controller mock exposing a peek-in picture object."""
    return MagicMock()


async def test_async_setup_entry_missing_unique_id_raises(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup raises ConfigEntryError when the config entry has no unique_id."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = None
    add_entities = MagicMock()

    with pytest.raises(ConfigEntryError):
        await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_not_called()


async def test_async_setup_entry_creates_entity(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup builds a single peek-in image entity."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], QolsysPicture_PeekIn)


async def test_unique_id_uses_config_unique_id(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """The unique id derives from the config entry unique_id, not a stale None."""
    entity = QolsysPicture_PeekIn(hass, controller, UID)
    assert entity.unique_id == f"{UID}_picture_peek_in"


async def test_image_entity_initialized_state_attributes(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Regression: ImageEntity.__init__ runs so state_attributes doesn't crash.

    Previously QolsysPicture_PeekIn only ran QolsysPanelEntity.__init__, leaving
    ImageEntity's ``access_tokens`` unset. ``async_write_ha_state`` during add
    reads ``state_attributes`` -> ``access_tokens[-1]`` and raised AttributeError.
    """
    entity = QolsysPicture_PeekIn(hass, controller, UID)

    # access_tokens is populated by ImageEntity.__init__ / async_update_token.
    assert entity.access_tokens

    # state_attributes is exactly what HA reads during async_write_ha_state.
    attrs = entity.state_attributes
    assert attrs is not None
    assert attrs["access_token"] == entity.access_tokens[-1]


async def test_async_image_returns_picture_data(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """async_image returns the current picture bytes."""
    entity = QolsysPicture_PeekIn(hass, controller, UID)
    entity._picture.data = b"jpeg-bytes"
    assert await entity.async_image() == b"jpeg-bytes"
