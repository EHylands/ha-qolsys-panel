import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableThermostat(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.ThermostatsContentProvider/thermostat"
        self._table = "thermostat"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "version",
            "opr",
            "partition_id",
            "thermostat_id",
            "thermostat_name",
            "current_temp",
            "target_cool_temp",
            "target_heat_temp",
            "target_temp",
            "power_usage",
            "thermostat_mode",
            "thermostat_mode_bitmask",
            "fan_mode",
            "fan_mode_bitmask",
            "set_point_mode",
            "set_point_mode_bitmask",
            "node_id",
            "created_by",
            "created_date",
            "updated_by",
            "last_updated_date",
            "thermostat_mode_updated_time",
            "fan_mode_updated_time",
            "set_point_mode_updated_time",
            "setpoint_capabilites",
            "target_cool_temp_updated_time",
            "target_heat_temp_updated_time",
            "current_temp_updated_time",
            "device_temp_unit",
            "endpoint",
            "paired_status",
            "configuration_parameter",
            "operating_state",
            "fan_state",
        ]

        self._create_table()
