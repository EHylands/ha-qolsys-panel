import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableDoorLock(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.DoorLocksContentProvider/doorlock"
        self._table = "doorlock"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "capabilities",
            "version",
            "opr",
            "partition_id",
            "doorlock_name",
            "status",
            "node_id",
            "created_by",
            "created_date",
            "updated_by",
            "last_updated_date",
            "remote_arming",
            "keyfob_arming",
            "panel_arming",
            "endpoint",
            "paired_status",
            "configuration",
        ]

        self._create_table()
