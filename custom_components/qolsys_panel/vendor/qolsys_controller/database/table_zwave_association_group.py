import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableZwaveAssociationGroup(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.ZwaveAssociationGroupContentProvider/zwave_association_group"
        self._table = "zwave_association_group"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "version",
            "opr",
            "partition_id",
            "group_name",
            "associated_nodes",
            "group_id",
            "created_date",
            "last_updated_date",
            "group_command_class",
            "max_supported_nodes",
            "node_id",
            "endpoint",
        ]

        self._create_table()
