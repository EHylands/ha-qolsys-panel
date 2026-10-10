import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableZwaveHistory(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.ZDeviceHistoryContentProvider/zwave_history"
        self._table = "zwave_history"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = False

        self._columns = [
            "_id",
            "version",
            "opr",
            "partition_id",
            "node_id",
            "device_name",
            "source",
            "event",
            "request",
            "response",
            "created_date",
            "updated_date",
            "last_updated_by",
            "field_type",
            "ack",
            "protocol",
        ]

        self._create_table()
