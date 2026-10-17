import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableZwaveNode(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.ZwaveContentProvider/zwave_node"
        self._table = "zwave_node"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "version",
            "opr",
            "partition_id",
            "node_id",
            "node_name",
            "node_type",
            "node_status",
            "node_secure_cmd_cls",
            "node_battery_level",
            "node_battery_level_value",
            "is_node_listening_node",
            "basic_report_value",
            "switch_multilevel_report_value",
            "basic_device_type",
            "generic_device_type",
            "specific_device_type",
            "num_secure_command_class",
            "secure_command_class",
            "manufacture_id",
            "product_type",
            "product_id",
            "library_type_version",
            "protocol_version",
            "protocol_sub_version",
            "application_version",
            "application_sub_version",
            "capability",
            "command_class_list",
            "lenof_command_class_list",
            "security",
            "library_type",
            "last_updated_date",
            "node_battery_level_updated_time",
            "basic_report_updated_time",
            "switch_multilevel_report_updated_time",
            "rediscover_status",
            "last_rediscover_time",
            "neighbour_info",
            "last_node_test_time",
            "notification_capabilities",
            "multi_channel_details",
            "endpoint",
            "endpoint_details",
            "device_wakeup_time",
            "role_type",
            "is_device_sleeping",
            "counters_passed",
            "counters_failed",
            "group_id",
            "command_classes_version",
            "paired_status",
            "device_dsk",
            "endpoint_secure_cmd_cls",
            "s2_security_keys",
            "device_protocol",
            "is_device_hidden",
            "ime_data",
            "device_status",
            "device_id",
            "all_command_classes",
            "sound_switch_info",
            "long_range_nodeid",
            "hide_device_info",
            "meter_capabilities",
            "multisensor_capabilities",
            "central_scene_supported",
        ]

        self._create_table()
