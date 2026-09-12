import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableAutomation(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.AutomationDeviceContentProvider/automation"
        self._table = "automation"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "virtual_node_id",
            "version",
            "opr",
            "partition_id",
            "end_point",
            "extras",
            "is_autolocking_enabled",
            "device_type",
            "endpoint_secure_cmd_classes",
            "automation_id",
            "device_name",
            "protocol",
            "node_battery_level_value",
            "state",
            "last_updated_date",
            "manufacturer_id",
            "endpoint_cmd_classes",
            "device_id",
            "nodeid_cmd_classes",
            "is_device_hidden",
            "nodeid_secure_cmd_classes",
            "created_date",
            "status",
            "smart_energy_optimizer",
            "linked_security_zone",
        ]

        self._create_table()
