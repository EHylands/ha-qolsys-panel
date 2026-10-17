import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableAlarmedSensor(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.AlarmedSensorProvider/alarmedsensor"
        self._table = "alarmedsensor"
        self._abort_on_error = True
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "partition_id",
            "silenced",
            "zone_id",
            "sgroup",
            "action",
            "timed_out",
            "type",
            "priority",
            "aseb_type",
            "alarm_time",
            "version",
            "opr",
        ]

        self._create_table()
