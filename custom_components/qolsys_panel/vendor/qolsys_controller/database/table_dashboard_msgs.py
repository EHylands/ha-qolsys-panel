import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableDashboardMsgs(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.DashboardMessagesContentProvider/dashboard_msgs"
        self._table = "dashboard_msgs"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "version",
            "opr",
            "partition_id",
            "msg_id",
            "title",
            "description",
            "received_time",
            "start_time",
            "end_time",
            "read",
            "mime_type",
            "type",
        ]

        self._create_table()
