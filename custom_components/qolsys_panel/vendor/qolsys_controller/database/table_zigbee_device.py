import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableZigbeeDevice(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.ZigbeeDeviceContentProvider/zigbee_device"
        self._table = "zigbee_device"
        self._implemented = True
        self._abort_on_error = False
        self._report_new_columns = True

        self._columns = [
            "_id",
        ]

        self._create_table()
