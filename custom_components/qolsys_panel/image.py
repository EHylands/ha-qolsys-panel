"""Support for Qolsys Panel Images."""

from __future__ import annotations

from datetime import datetime

from qolsys_controller import qolsys_controller
from qolsys_controller.enum_qolsys import QolsysNotification
from qolsys_controller.media_picture import QolsysPicture

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysPanelEntity
from .types import QolsysPanelConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    QolsysPanel = config_entry.runtime_data
    if (unique_id := config_entry.unique_id) is None:
        raise ConfigEntryError("Config entry has no unique_id; re-add the integration")

    entities: list[ImageEntity] = []
    peek_in_picture = QolsysPicture_PeekIn(hass, QolsysPanel, unique_id)
    entities.append(peek_in_picture)
    async_add_entities(entities)


class QolsysPicture_PeekIn(QolsysPanelEntity, ImageEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        QolsysPanel: qolsys_controller,
        unique_id: str,
    ) -> None:
        super().__init__(QolsysPanel, unique_id)
        # QolsysPanelEntity.__init__ doesn't chain to ImageEntity, so initialize
        # it explicitly to set up access_tokens and the HTTP client.
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = f"{unique_id}_picture_peek_in"
        self._picture: QolsysPicture = QolsysPanel.state.picture_peek_in
        self._attr_name = "Peek In Picture"

    @property
    def content_type(self) -> str:
        return self._picture.image_type

    @property
    def image_last_updated(self) -> datetime | None:
        return self._picture.lastupdate

    async def async_added_to_hass(self) -> None:
        """Observe connection_status changes."""
        self.QolsysPanel.state.picture_peek_in.register(
            QolsysNotification.QOLSYS_PICTURE_UPDATE, self.schedule_update_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing connection_status changes."""
        self.QolsysPanel.state.picture_peek_in.unregister(
            QolsysNotification.QOLSYS_PICTURE_UPDATE, self.schedule_update_ha_state
        )

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return self._picture.data
