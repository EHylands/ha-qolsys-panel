import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableHistory(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.HistoryContentProvider/history"
        self._table = "history"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = False

        self._columns = [
            "_id",
            "version",
            "opr",
            "partition_id",
            "device",
            "events",
            "time",
            "ack",
            "type",
            "feature1",
            "feature2",
            "device_id",
            # "history_bulk_insert",
            "Partition",
            # "History_Device_Names_List",
            # "History Bypass Event",
        ]

        self._create_table()
