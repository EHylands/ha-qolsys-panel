import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableCountryLocale(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.CountryLocaleContentProvider/country_locale"
        self._table = "country_locale"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "version",
            "opr",
            "partition_id",
            "country",
            "language",
            "alpha2_code",
            "language_code",
            "date_format_enum",
            "hour_format",
            "temp_format",
            "is_active",
            "date_separator",
            "zwave_region_frequency_code",
            "zwave_region_frequency",
            "zwave_region_prop_values",
        ]

        self._create_table()
