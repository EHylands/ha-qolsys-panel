import logging
import time
from typing import Any

from .enum_qolsys import QolsysNotification
from .observable import Event, QolsysObservable

LOGGER = logging.getLogger(__name__)


class QolsysForecast:
    def __init__(self, data: dict[str, str]) -> None:
        self._high_temp: str = data.get("high_temp", "")
        self._low_temp: str = data.get("low_temp", "")
        self._day_of_week: str = data.get("day_of_week", "")
        self._condition: str = data.get("condition", "")
        self._icon: str = data.get("icon", "")
        self._precipitation: str = data.get("precipitation", "")
        self._current_weather_date: str = data.get("current_weather_date", "")

    @property
    def high_temp(self) -> float | None:
        try:
            return float(self._high_temp)
        except ValueError:
            return None

    @property
    def low_temp(self) -> float | None:
        try:
            return float(self._low_temp)
        except ValueError:
            return None

    @property
    def day_of_week(self) -> str:
        return self._day_of_week

    @property
    def condition(self) -> str:
        return self._condition

    @property
    def precipitation(self) -> int | None:
        try:
            return int(self._precipitation)
        except ValueError:
            return None

    @property
    def current_weather_date(self) -> str:
        return self._current_weather_date

    def to_dict_event(self) -> dict[str, Any]:
        return {
            "high_temp": self.high_temp,
            "low_temp": self.low_temp,
            "day_of_week": self.day_of_week,
            "condition": self.condition,
            "precipitation": self.precipitation,
            "current_weather_date": self.current_weather_date,
        }


class QolsysWeather(QolsysObservable):
    def __init__(self) -> None:
        super().__init__()
        self._forecasts: list[QolsysForecast] = []

    def current_weather(self) -> QolsysForecast | None:
        if self._forecasts:
            return self._forecasts[0]
        return None

    def update(self, data: list[QolsysForecast]) -> None:
        self._forecasts.clear()
        for forecast_data in data:
            self._forecasts.append(forecast_data)

        self.notify(Event(QolsysNotification.WEATHER_UPDATE, self, self.to_dict_event()))

    @property
    def forecasts(self) -> list[QolsysForecast]:
        return self._forecasts

    def to_dict_event(self) -> dict[str, Any]:
        return {
            "type": "weather",
            "state": {
                "forescast": [forecast.to_dict_event() for forecast in self._forecasts],
            },
            "attributes": {},
            "ts": time.time_ns() // 1_000_000,
            "version": 1,
        }
