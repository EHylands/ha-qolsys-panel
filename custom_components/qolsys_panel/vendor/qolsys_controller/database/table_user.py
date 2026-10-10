import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableUser(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.UserContentProvider/user"
        self._table = "user"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "version",
            "opr",
            "partition_id",
            "username",
            "userPin",
            "expirydate",
            "usertype",
            "userid",
            "lastname",
            "check_in",
            "hash_user",
            "updated_date",
            "updated_by",
            "created_date",
            "created_by",
            "user_permissions",
            "door_locks",
            "active_duration_type",
            "active",
            "start_date",
            "tag_flag",
            "check_in_time",
            "user_feature1",
            "user_feature2",
        ]

        self._create_table()
