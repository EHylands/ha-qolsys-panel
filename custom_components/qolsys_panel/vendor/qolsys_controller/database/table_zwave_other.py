import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableZwaveOther(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.ZwaveOtherDeviceContentProvider/zwave_other"
        self._table = "zwave_other"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "created_date",
            "capabilities",
            "device_name",
            "device_params_1",
            "device_params_2",
            "endpoint",
            "last_updated_date",
            "node_id",
            "node_type",
            "opr",
            "paired_status",
            "partition_id",
            "status",
            "version",
        ]

        self._create_table()
