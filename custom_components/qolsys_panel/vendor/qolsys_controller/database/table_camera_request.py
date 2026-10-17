import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysCameraRequest(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.CameraRequestContentProvider/camerarequest"
        self._table = "camerarequest"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "request_id",
            "type",
            "description",
            "name",
            "file_type",
            "create_time",
            "update_time",
            "source",
            "event_index",
            "short_id",
            "user_id",
            "zone_id",
            "camera_source",
            "imageId",
        ]

        self._create_table()
