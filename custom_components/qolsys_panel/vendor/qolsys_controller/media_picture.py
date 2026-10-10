from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone

from .enum_qolsys import PhotoDirectory, QolsysNotification
from .observable import Event, QolsysObservable

LOGGER = logging.getLogger(__name__)


class QolsysPicture(QolsysObservable):
    def __init__(
        self,
        image_type: str = "image/jpeg",
        data: bytes | None = None,
        request_id: str = "",
        filename: str = "",
        directory: PhotoDirectory = PhotoDirectory.PEEK_IN,
        retained_on_panel: bool = False,
    ) -> None:
        super().__init__()
        self._data: bytes | None = data
        self._image_type: str = image_type
        self._request_id: str = request_id
        self._filename: str = filename
        self._directory: PhotoDirectory = directory
        self._retained_on_panel: bool = retained_on_panel
        self._lastupdate: datetime | None = None

    def update(self, new_picture: QolsysPicture) -> None:
        self.start_batch_update()
        self.image_type = new_picture.image_type
        self.request_id = new_picture.request_id
        self.filename = new_picture.filename
        self.directory = new_picture.directory
        self.retained_on_panel = new_picture.retained_on_panel
        self.data = new_picture.data
        self.end_batch_update()

    def write_to_directory(self, path: str) -> None:
        """Write the picture to the specified directory."""
        if self._data is not None:
            with open(path, "wb") as f:
                f.write(self._data)

    def to_dict(self) -> dict[str, str]:
        return {
            "image_type": self.image_type,
            "request_id": self.request_id,
            "filename": self.filename,
            "directory": self.directory.value,
            "retained_on_panel": str(self.retained_on_panel),
            "data": base64.b64encode(self._data).decode("ascii") if self._data is not None else "",
        }

    def to_dict_event(self) -> dict[str, str]:
        return {
            "image_type": self.image_type,
            "request_id": self.request_id,
            "filename": self.filename,
            "directory": self.directory.value,
            "retained_on_panel": str(self.retained_on_panel),
            "lastupdate": str(self._lastupdate),
        }

    # -----------------------------
    # properties + setters
    # -----------------------------

    @property
    def data(self) -> bytes | None:
        return self._data

    @data.setter
    def data(self, value: bytes | None) -> None:
        self._data = value
        self._lastupdate = datetime.now(timezone.utc)
        self.notify(Event(QolsysNotification.QOLSYS_PICTURE_UPDATE, self, self.to_dict_event()))

    @property
    def image_type(self) -> str:
        return self._image_type

    @image_type.setter
    def image_type(self, value: str) -> None:
        if self._image_type != value:
            self._image_type = value
            self._lastupdate = datetime.now(timezone.utc)
            self.notify(Event(QolsysNotification.QOLSYS_PICTURE_UPDATE, self, self.to_dict_event()))

    @property
    def request_id(self) -> str:
        return self._request_id

    @request_id.setter
    def request_id(self, value: str) -> None:
        if self._request_id != value:
            self._request_id = value
            self._lastupdate = datetime.now(timezone.utc)
            self.notify(Event(QolsysNotification.QOLSYS_PICTURE_UPDATE, self, self.to_dict_event()))

    @property
    def filename(self) -> str:
        return self._filename

    @filename.setter
    def filename(self, value: str) -> None:
        if self._filename != value:
            self._filename = value
            self._lastupdate = datetime.now(timezone.utc)
            self.notify(Event(QolsysNotification.QOLSYS_PICTURE_UPDATE, self, self.to_dict_event()))

    @property
    def directory(self) -> PhotoDirectory:
        return self._directory

    @directory.setter
    def directory(self, value: PhotoDirectory) -> None:
        if self._directory != value:
            self._directory = value
            self._lastupdate = datetime.now(timezone.utc)
            self.notify(Event(QolsysNotification.QOLSYS_PICTURE_UPDATE, self, self.to_dict_event()))

    @property
    def retained_on_panel(self) -> bool:
        return self._retained_on_panel

    @retained_on_panel.setter
    def retained_on_panel(self, value: bool) -> None:
        if self._retained_on_panel != value:
            self._retained_on_panel = value
            self._lastupdate = datetime.now(timezone.utc)
            self.notify(Event(QolsysNotification.QOLSYS_PICTURE_UPDATE, self, self.to_dict_event()))

    @property
    def lastupdate(self) -> datetime | None:
        return self._lastupdate
