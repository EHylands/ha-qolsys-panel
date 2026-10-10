"""Tests for the Qolsys Panel Peek-In image entity."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from conftest import PANEL_MAC
import pytest

from custom_components.qolsys_panel.const import DOMAIN, OPTION_PEEK_IN_PICTURE
from custom_components.qolsys_panel.image import (
    PeekInPicture,
    async_setup_entry,
    peek_in_unique_id,
)
from custom_components.qolsys_panel.vendor.qolsys_controller.enum_qolsys import (
    QolsysNotification,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

UID = PANEL_MAC


@pytest.fixture
def controller() -> MagicMock:
    """A controller mock exposing a peek-in picture object."""
    return MagicMock()


def _entry(controller: MagicMock, options: dict | None = None) -> MagicMock:
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    config_entry.options = options or {}
    return config_entry


async def test_async_setup_entry_missing_unique_id_raises(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup raises ValueError, not ConfigEntryNotReady, without a unique_id (review N5)."""
    config_entry = _entry(controller)
    config_entry.unique_id = None
    add_entities = MagicMock()

    with pytest.raises(ValueError):
        await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_not_called()


async def test_async_setup_entry_creates_entity_by_default(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """With no option stored the entity is created (the default is on)."""
    add_entities = MagicMock()

    await async_setup_entry(hass, _entry(controller), add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], PeekInPicture)


async def test_async_setup_entry_option_off_adds_nothing(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Option off: no entity, and no registry lookup error when none existed."""
    add_entities = MagicMock()

    await async_setup_entry(
        hass, _entry(controller, {OPTION_PEEK_IN_PICTURE: False}), add_entities
    )

    add_entities.assert_not_called()


async def test_async_setup_entry_option_off_removes_registered_entity(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Turning the option off removes the entity an earlier run registered."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_or_create(
        "image", DOMAIN, peek_in_unique_id(UID)
    ).entity_id
    assert registry.async_get(entity_id) is not None

    await async_setup_entry(
        hass, _entry(controller, {OPTION_PEEK_IN_PICTURE: False}), MagicMock()
    )

    assert registry.async_get(entity_id) is None


async def test_unique_id_uses_config_unique_id(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """The unique id derives from the config entry unique_id, upstream's format."""
    entity = PeekInPicture(hass, controller, UID)
    assert entity.unique_id == f"{UID}_picture_peek_in"


async def test_image_entity_initialized_state_attributes(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """ImageEntity.__init__ runs, so the access token HA writes as state exists.

    QolsysPanelEntity.__init__ does not chain; without the explicit call
    ``access_tokens`` is unset and the first async_write_ha_state raises.
    """
    entity = PeekInPicture(hass, controller, UID)

    assert entity.access_tokens
    attrs = entity.state_attributes
    assert attrs is not None
    assert attrs["access_token"] == entity.access_tokens[-1]


async def test_async_image_returns_picture_data(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """async_image returns the current picture bytes and content type."""
    entity = PeekInPicture(hass, controller, UID)
    entity._picture.data = b"jpeg-bytes"
    entity._picture.image_type = "image/jpeg"
    assert await entity.async_image() == b"jpeg-bytes"
    assert entity.content_type == "image/jpeg"


async def test_async_image_none_before_first_capture(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Before any capture there is no photo and no last-updated time."""
    entity = PeekInPicture(hass, controller, UID)
    entity._picture.data = None
    entity._picture.lastupdate = None
    assert await entity.async_image() is None
    assert entity.image_last_updated is None


async def test_image_last_updated_tracks_picture(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """image_last_updated is the picture's own timestamp, so HA's cache turns over."""
    entity = PeekInPicture(hass, controller, UID)
    when = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    entity._picture.lastupdate = when
    assert entity.image_last_updated == when


async def test_observes_picture_updates_with_the_threadsafe_handler(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """The entity registers _handle_update (audit M4), on the picture and the panel."""
    entity = PeekInPicture(hass, controller, UID)

    await entity.async_added_to_hass()
    controller.state.picture_peek_in.register.assert_called_once_with(
        QolsysNotification.QOLSYS_PICTURE_UPDATE, entity._handle_update
    )
    controller.state.register.assert_called_once_with(
        QolsysNotification.PANEL_STATUS_UPDATE, entity._handle_update
    )

    await entity.async_will_remove_from_hass()
    controller.state.picture_peek_in.unregister.assert_called_once_with(
        QolsysNotification.QOLSYS_PICTURE_UPDATE, entity._handle_update
    )
    controller.state.unregister.assert_called_once_with(
        QolsysNotification.PANEL_STATUS_UPDATE, entity._handle_update
    )
