import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTablePowerGDevice(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.PowerGDeviceContentProvider/powerg_device"
        self._table = "powerg_device"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "avg_link_quality",
            "battery_voltage",
            "capabilities",
            "dealer_code",
            "extras",
            "firmware_version",
            "led",
            "light",
            "link_quality",
            "link_status",
            "longID",
            "manufacturing_id",
            "notification_period",
            "opr",
            "parent_node",
            "partition_id",
            "radio_id",
            "radio_version",
            "shortID",
            "status_data",
            "supported_type",
            "temperature",
            "version",
            "writeable_capabilities",
        ]

        self._create_table()
