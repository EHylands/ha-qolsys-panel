"""Support for Qolsys Panel Weather."""

from __future__ import annotations

from datetime import UTC, datetime
import logging

from qolsys_controller import qolsys_controller

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysWeatherEntity
from .types import QolsysPanelConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Weather."""
    entities: list[WeatherSensor] = []
    QolsysPanel = config_entry.runtime_data
    unique_id = config_entry.unique_id
    assert unique_id is not None
    entities.append(WeatherSensor(QolsysPanel, unique_id))
    async_add_entities(entities)


class WeatherSensor(QolsysWeatherEntity, WeatherEntity):
    """An Weather Entity for Qolsys Panel."""

    _attr_has_entity_name = False

    def __init__(self, QolsysPanel: qolsys_controller, unique_id: str) -> None:
        """Initialise a Qolsys Weather entity."""
        super().__init__(QolsysPanel, unique_id)
        self._attr_unique_id = self._weather_unique_id
        self._attr_name = "Weather"
        self._attr_native_temperature_unit = "°F"
        self._attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

    @property
    def condition(self) -> str:
        current = self._weather.current_weather()
        if current is not None:
            return current.condition

        return ""

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        if self._weather:
            if self._weather.forecasts:
                forecasts = []

                for daily in self._weather.forecasts:
                    raw_timestamp = daily.current_weather_date

                    try:
                        timestamp = int(raw_timestamp)
                    except ValueError:
                        _LOGGER.error(
                            "Invalid timestamp '%s' in daily forecast", raw_timestamp
                        )
                        continue

                    dt = datetime.fromtimestamp(timestamp / 1000, tz=UTC)

                    forecast: Forecast = {
                        "datetime": dt.isoformat(),
                        "condition": daily.condition,
                        "native_temperature": daily.high_temp,
                        "native_templow": daily.low_temp,
                        "precipitation_probability": daily.precipitation,
                    }
                    forecasts.append(forecast)
                return forecasts
        return None
