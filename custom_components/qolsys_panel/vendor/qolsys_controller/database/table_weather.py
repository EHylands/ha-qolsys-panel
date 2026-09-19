import logging  # noqa: INP001
import sqlite3

from .table import QolsysTable

LOGGER = logging.getLogger(__name__)


class QolsysTableWeather(QolsysTable):
    def __init__(self, db: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
        super().__init__(db, cursor)
        self._uri = "content://com.qolsys.qolsysprovider.ForecastWeatherContentProvider/weather"
        self._table = "weather"
        self._abort_on_error = False
        self._implemented = True
        self._report_new_columns = True

        self._columns = [
            "_id",
            "version",
            "opr",
            "partition_id",
            "high_temp",
            "low_temp",
            "day_of_week",
            "condition",
            "icon",
            "precipitation",
            "current_weather_date",
        ]

        self._create_table()
