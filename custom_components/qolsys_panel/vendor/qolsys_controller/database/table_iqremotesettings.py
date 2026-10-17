import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableIqRemoteSettings(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.IQRemoteSettingsContentProvider/iqremotesettings"
        self._table = "iqremotesettings"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "version",
            "opr",
            "partition_id",
            "zone_id",
            "mac_address",
            "name",
            "value",
        ]

        self._create_table()
