import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableSensor(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.SensorContentProvider/sensor"
        self._table = "sensor"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "version",
            "opr",
            "partition_id",
            "ac_status",
            "sensorid",
            "sensortype",
            "sensorname",
            "sensorgroup",
            "chimetype",
            "sensorstatus",
            "time",
            "sensorstate",
            "sensortts",
            "zoneid",
            "frame_id",
            "zone_alarm_type",
            "zone_equipment_code",
            "zone_physical_type",
            "zone_type",
            "zone_rf_sensor",
            "zone_supervised",
            "zone_two_way_voice_enabled",
            "zone_reporting_enabled",
            "zone_feature1",
            "zone_feature2",
            "zone_feature3",
            "battery_status",
            "created_date",
            "created_by",
            "updated_date",
            "updated_by",
            "frame_count",
            "frame_type",
            "current_capability",
            "shortID",
            "diag_24hr",
            "allowdisarming",
            "device_capability",
            "sub_type",
            "signal_source",
            "powerg_manufacture_id",
            "parent_node",
            "latestdBm",
            "averagedBm",
            "serial_number",
            "secondary_panel_mac_address",
            "extras",
            "allowspeaker",
            "firmware_version",
            "radio_version",
            "radio_id",
        ]

        self._create_table()
