"""The panel camera's Peek-In photo as a Home Assistant image entity.

The IQ Panel has a camera on its face. Upstream 1.9.0 exposes the most recent
Peek-In photo as an image entity on the panel device, refreshed by the
`qolsys_panel.update_picture_peek_in` service (services.py), which is the only
thing that ever takes a photo: the entity itself never captures. Both are
gated by the "Enable Peek In Picture" option; off, no entity exists and the
service refuses. The bytes come from the panel over the paired MQTT
connection (vendor/qolsys_controller/commands/camera.py), never from the
network, and Home Assistant serves them through its normal image proxy with
its own access tokens.
"""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN, ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEFAULT_PEEK_IN_PICTURE, DOMAIN, OPTION_PEEK_IN_PICTURE
from .entity import QolsysPanelEntity
from .types import QolsysPanelConfigEntry
from .vendor.qolsys_controller import qolsys_controller
from .vendor.qolsys_controller.enum_qolsys import QolsysNotification
from .vendor.qolsys_controller.media_picture import QolsysPicture

PARALLEL_UPDATES = 0


def peek_in_unique_id(panel_unique_id: str) -> str:
    """The image entity's unique_id (upstream's, so an upstream install keeps its entity)."""
    return f"{panel_unique_id}_picture_peek_in"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Peek-In image entity, or remove it when the option is off."""
    QolsysPanel = config_entry.runtime_data
    if (unique_id := config_entry.unique_id) is None:
        # A forwarded platform must not raise ConfigEntryNotReady: HA logs a
        # complaint rather than retrying, and __init__.async_setup_entry already
        # refuses a None unique_id before any platform is set up (review N5).
        raise ValueError("Config entry has no unique_id; re-add the integration")

    if not config_entry.options.get(OPTION_PEEK_IN_PICTURE, DEFAULT_PEEK_IN_PICTURE):
        # Off means gone, not "unavailable, still showing the last photo": the
        # options flow reloads the entry, so drop the registry entry an earlier
        # run with the option on left behind.
        registry = er.async_get(hass)
        entity_id = registry.async_get_entity_id(
            IMAGE_DOMAIN, DOMAIN, peek_in_unique_id(unique_id)
        )
        if entity_id is not None:
            registry.async_remove(entity_id)
        return

    async_add_entities([PeekInPicture(hass, QolsysPanel, unique_id)])


class PeekInPicture(QolsysPanelEntity, ImageEntity):
    """The most recent Peek-In photo."""

    _attr_name = "Peek In Picture"

    def __init__(
        self, hass: HomeAssistant, QolsysPanel: qolsys_controller, unique_id: str
    ) -> None:
        """Set up the entity on the panel device."""
        super().__init__(QolsysPanel, unique_id)
        # QolsysPanelEntity.__init__ does not chain, so ImageEntity's own
        # __init__ (the access tokens and the HTTP client) is run explicitly.
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = peek_in_unique_id(unique_id)
        self._picture: QolsysPicture = QolsysPanel.state.picture_peek_in

    @property
    def content_type(self) -> str:
        """The photo's MIME type (image/jpeg)."""
        return self._picture.image_type

    @property
    def image_last_updated(self) -> datetime | None:
        """When the photo was last replaced; None until the first capture."""
        return self._picture.lastupdate

    async def async_added_to_hass(self) -> None:
        """Observe the picture, and the panel connection for availability."""
        await super().async_added_to_hass()
        self._picture.register(
            QolsysNotification.QOLSYS_PICTURE_UPDATE, self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing."""
        await super().async_will_remove_from_hass()
        self._picture.unregister(
            QolsysNotification.QOLSYS_PICTURE_UPDATE, self._handle_update
        )

    async def async_image(self) -> bytes | None:
        """The photo's bytes, or None before the first capture."""
        return self._picture.data
