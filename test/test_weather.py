"""Tests for the Qolsys Panel weather."""

from unittest.mock import MagicMock

from conftest import PANEL_MAC
import pytest

from custom_components.qolsys_panel.weather import WeatherSensor, async_setup_entry
from homeassistant.core import HomeAssistant

UID = PANEL_MAC


@pytest.fixture
def controller() -> MagicMock:
    """A controller mock exposing a weather object."""
    return MagicMock()


def _daily(date: str) -> MagicMock:
    """Build a daily-forecast mock."""
    daily = MagicMock()
    daily.current_weather_date = date
    daily.condition = "Cloudy"
    daily.high_temp = 70
    daily.low_temp = 50
    daily.precipitation = 10
    return daily


async def test_async_setup_entry_creates_entities(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup builds a single weather entity."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], WeatherSensor)


def test_condition_present(controller: MagicMock) -> None:
    """The condition reflects the current weather when available."""
    weather = WeatherSensor(controller, UID)
    weather._weather.current_weather.return_value = MagicMock(condition="Sunny")
    assert weather.condition == "Sunny"


def test_condition_absent(controller: MagicMock) -> None:
    """The condition is empty when there is no current weather."""
    weather = WeatherSensor(controller, UID)
    weather._weather.current_weather.return_value = None
    assert weather.condition == ""


async def test_forecast_daily(controller: MagicMock) -> None:
    """A valid daily forecast is converted; invalid timestamps are skipped."""
    weather = WeatherSensor(controller, UID)
    weather._weather.forecasts = [_daily("1700000000000"), _daily("not-a-number")]

    forecast = await weather.async_forecast_daily()

    assert len(forecast) == 1
    assert forecast[0]["condition"] == "Cloudy"
    assert forecast[0]["native_temperature"] == 70
    assert forecast[0]["native_templow"] == 50
    assert forecast[0]["precipitation_probability"] == 10


async def test_forecast_daily_empty(controller: MagicMock) -> None:
    """No forecasts returns None."""
    weather = WeatherSensor(controller, UID)
    weather._weather.forecasts = []
    assert await weather.async_forecast_daily() is None
