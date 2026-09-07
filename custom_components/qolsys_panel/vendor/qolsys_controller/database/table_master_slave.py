import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableMasterSlave(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.MasterSlaveContentProvider/master_slave"
        self._table = "master_slave"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "version",
            "opr",
            "partition_id",
            "zone_id",
            "ip_address",
            "mac_address",
            "device_type",
            "created_by",
            "created_date",
            "updated_by",
            "last_updated_date",
            "status",
            "device_name",
            "last_updated_iq_remote_checksum",
            "software_version",
            "upgrade_status",
            "name",
            "bssid",
            "ssid",
            "dhcpInfo",
            "topology",
            "reboot_reason",
            "field_remote_camera_streaming",
        ]

        self._create_table()
