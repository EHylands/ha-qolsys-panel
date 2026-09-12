import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableDimmerLight(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.DimmerLightsContentProvider/dimmerlight"
        self._table = "dimmerlight"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "version",
            "opr",
            "partition_id",
            "dimmer_name",
            "status",
            "node_id",
            "level",
            "created_by",
            "created_date",
            "updated_by",
            "last_updated_date",
            "endpoint",
            "power_details",
            "paired_status",
        ]

        self._create_table()
