import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableVirtualDevice(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.VirtualDeviceContentProvider/virtual_device"
        self._table = "virtual_device"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "version",
            "opr",
            "partition_id",
            "device_id",
            "name",
            "type",
            "func_list",
            "create_time",
            "created_by",
            "update_time",
            "updated_by",
            "device_zone_list",
        ]

        self._create_table()
