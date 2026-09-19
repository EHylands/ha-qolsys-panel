import logging
from datetime import datetime, timezone
from typing import Any

from .enum_qolsys import QolsysNotification
from .observable import Event, QolsysObservable

LOGGER = logging.getLogger(__name__)


class QolsysScene(QolsysObservable):
    def __init__(self, data: dict[str, str]) -> None:
        super().__init__()

        self._scene_id: str = data.get("scene_id", "")
        self._name: str = data.get("name", "")
        self._icon: str = data.get("icon", "")
        self._color: str = data.get("color", "")

    def update(self, data: dict[str, str]) -> None:
        scene_id_update = data.get("scene_id", "")
        if scene_id_update != self._scene_id:
            LOGGER.error("Updating Scene%s (%s) with Scene%s (different id)", self._scene_id, self.name, scene_id_update)
            return

        self.start_batch_update()

        # Update name
        if "name" in data:
            self.sensorname = data.get("name", "")

        if "color" in data:
            self.color = data.get("color", "")

        if "icon" in data:
            self.icon = data.get("icon", "")

        self.end_batch_update()

    def to_dict(self) -> dict[str, str]:
        return {
            "scene_id": self.scene_id,
            "name": self.name,
            "color": self.color,
            "icon": self.icon,
        }

    # -----------------------------
    # properties + setters
    # -----------------------------

    @property
    def scene_id(self) -> str:
        return self._scene_id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if self._name != value:
            self._name = value
            self.notify(Event(QolsysNotification.SCENE_UPDATE, self, self.to_dict_event()))

    @property
    def icon(self) -> str:
        return self._icon

    @icon.setter
    def icon(self, value: str) -> None:
        if self._icon != value:
            self._icon = value
            self.notify(Event(QolsysNotification.SCENE_UPDATE, self, self.to_dict_event()))

    @property
    def color(self) -> str:
        return self._color

    @color.setter
    def color(self, value: str) -> None:
        if self._color != value:
            self._color = value
            self.notify(Event(QolsysNotification.SCENE_UPDATE, self, self.to_dict_event()))

    def to_dict_event(self) -> dict[str, Any]:
        return {
            "id": int(self.scene_id),
            "type": "scene",
            "attributes": {
                "name": self.name,
                "icon": self.icon,
                "color": self.color,
            },
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "version": 1,
        }
