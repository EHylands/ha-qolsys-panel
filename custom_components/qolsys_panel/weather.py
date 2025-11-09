"""Support for Qolsys Panel Weather."""

from __future__ import annotations

import logging

from datetime import datetime, timezone

from qolsys_controller import qolsys_controller
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.components.weather import WeatherEntity, WeatherEntityFeature, Forecast

from .types import QolsysPanelConfigEntry
from .entity import QolsysWeatherEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Weather."""
    entities: list[WeatherSensor] = []
    QolsysPanel = config_entry.runtime_data
    entities.append(WeatherSensor(QolsysPanel,config_entry.unique_id))
    async_add_entities(entities)

class WeatherSensor(QolsysWeatherEntity,WeatherEntity):
    """An Weather Entity for Qolsys Panel."""

    _attr_has_entity_name = False
    
    def __init__(
        self, 
        QolsysPanel: qolsys_controller, 
        unique_id: str
    ) -> None:
        """Initialise a Qolsys Weather entity."""
        super().__init__(QolsysPanel, unique_id)
        self._attr_unique_id = self._weather_unique_id
        self._attr_name = "Qolsys Panel - Weather"
        self._attr_native_temperature_unit = "°F"
        self._attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        if self._weather:
            if self._weather.forecasts: 
                forecasts = []
                
                for daily in self._weather.forecasts:
                    timestamp = daily.get("current_weather_date")
                    timestamp = int(timestamp)
                    timestamp = int(timestamp/1000)
                    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)

                    forecast: Forecast = {
                        "datetime": dt.isoformat(),
                        "condition": daily.condition,
                        "native_temperature": daily.high_temp,
                        "native_templow": daily.low_temp,
                        "precipitation_probability": daily.precipitation,
                    }
                    forecasts.append(forecast)
                _LOGGER.debug(forecasts)
                return forecasts
        return None