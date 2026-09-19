import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableSmartSocket(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.SmartSocketsContentProvider/smartsocket"
        self._table = "smartsocket"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "created_by",
            "created_date",
            "last_updated_date",
            "node_id",
            "paired_status",
            "power_usage",
            "status",
            "updated_by",
            "socket_id",
            "socket_name",
            "current_usagevoltage_usage",
        ]

        self._create_table()
