"""Tests for the Qolsys Panel climate entities."""

from unittest.mock import AsyncMock, MagicMock

from conftest import PANEL_MAC
import pytest
from qolsys_controller.enum_qolsys import QolsysHvacMode, QolsysTemperatureUnit

from custom_components.qolsys_panel.climate import (
    AutomationDevice_Climate,
    async_setup_entry,
)
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant

UID = PANEL_MAC


@pytest.fixture
def controller() -> MagicMock:
    """A controller mock with one automation device."""
    c = MagicMock()
    service = MagicMock()
    service.endpoint = 0
    device = MagicMock()
    device.virtual_node_id = "5"
    device.service_get_protocol.return_value = [service]
    c.state.automation_devices = [device]
    return c


def _climate(controller: MagicMock) -> AutomationDevice_Climate:
    """Build a climate entity with awaitable service commands."""
    entity = AutomationDevice_Climate(controller, "5", 0, UID)
    entity._service.set_hvac_mode = AsyncMock()
    entity._service.set_fan_mode = AsyncMock()
    entity._service.turn_off = AsyncMock()
    entity._service.set_temperature = AsyncMock()
    return entity


async def test_async_setup_entry_creates_entities(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup builds a climate entity per thermostat service."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], AutomationDevice_Climate)


@pytest.mark.parametrize(
    ("hvac_mode", "expected_attr"),
    [
        (QolsysHvacMode.AUTO, None),
        (QolsysHvacMode.HEAT_COOL, None),
        (QolsysHvacMode.OFF, None),
        (QolsysHvacMode.HEAT, "target_heat_temp"),
        (QolsysHvacMode.COOL, "target_cool_temp"),
        (QolsysHvacMode.FAN_ONLY, None),
    ],
)
def test_target_temperature(controller: MagicMock, hvac_mode, expected_attr) -> None:
    """Target temperature depends on the HVAC mode."""
    climate = _climate(controller)
    climate._service.hvac_mode = hvac_mode
    climate._service.target_heat_temp = 68
    climate._service.target_cool_temp = 74

    if expected_attr is None:
        assert climate.target_temperature is None
    else:
        assert climate.target_temperature == getattr(climate._service, expected_attr)


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        (QolsysTemperatureUnit.CELSIUS, UnitOfTemperature.CELSIUS),
        (QolsysTemperatureUnit.FAHRENHEIT, UnitOfTemperature.FAHRENHEIT),
    ],
)
def test_temperature_unit(controller: MagicMock, unit, expected) -> None:
    """Temperature unit maps the device unit."""
    climate = _climate(controller)
    climate._service.device_temperature_unit = unit
    assert climate.temperature_unit == expected


@pytest.mark.parametrize(
    ("hvac_mode", "high", "low"),
    [
        (QolsysHvacMode.AUTO, 74, 68),
        (QolsysHvacMode.HEAT_COOL, 74, 68),
        (QolsysHvacMode.HEAT, None, None),
    ],
)
def test_target_temperature_range(controller: MagicMock, hvac_mode, high, low) -> None:
    """The high/low targets are exposed only in auto/heat-cool modes."""
    climate = _climate(controller)
    climate._service.hvac_mode = hvac_mode
    climate._service.target_cool_temp = 74
    climate._service.target_heat_temp = 68
    assert climate.target_temperature_high == high
    assert climate.target_temperature_low == low


def test_passthrough_properties(controller: MagicMock) -> None:
    """Simple properties pass through to the backing service."""
    climate = _climate(controller)
    climate._service.current_temperature = 70
    climate._service.current_humidity = 45
    climate._service.min_temp = 50
    climate._service.max_temp = 90

    assert climate.current_temperature == 70
    assert climate.current_humidity == 45
    assert climate.min_temp == 50
    assert climate.max_temp == 90
    # fan/hvac accessors return the service values directly
    assert climate.fan_mode == climate._service.fan_mode
    assert climate.fan_modes == climate._service.fan_modes
    assert climate.hvac_action == climate._service.hvac_action
    assert climate.hvac_mode == climate._service.hvac_mode
    assert climate.hvac_modes == climate._service.hvac_modes


async def test_set_hvac_mode(controller: MagicMock) -> None:
    """Setting the HVAC mode forwards to the service."""
    climate = _climate(controller)
    await climate.async_set_hvac_mode(QolsysHvacMode.HEAT)
    climate._service.set_hvac_mode.assert_awaited_once_with(QolsysHvacMode.HEAT)


async def test_turn_off(controller: MagicMock) -> None:
    """Turning off forwards to the service."""
    climate = _climate(controller)
    await climate.async_turn_off()
    climate._service.turn_off.assert_awaited_once()


async def test_set_fan_mode(controller: MagicMock) -> None:
    """Setting the fan mode forwards to the service."""
    climate = _climate(controller)
    await climate.async_set_fan_mode("auto")
    climate._service.set_fan_mode.assert_awaited_once_with("auto")


async def test_set_temperature_high_low(controller: MagicMock) -> None:
    """High/low target temperatures map to cool/heat set points."""
    climate = _climate(controller)
    await climate.async_set_temperature(
        **{ATTR_TARGET_TEMP_HIGH: 76, ATTR_TARGET_TEMP_LOW: 66}
    )
    climate._service.set_temperature.assert_any_await(76, QolsysHvacMode.COOL)
    climate._service.set_temperature.assert_any_await(66, QolsysHvacMode.HEAT)


async def test_set_temperature_single(controller: MagicMock) -> None:
    """A single target temperature uses the current HVAC mode."""
    climate = _climate(controller)
    climate._service.hvac_mode = QolsysHvacMode.HEAT
    await climate.async_set_temperature(**{ATTR_TEMPERATURE: 72})
    climate._service.set_temperature.assert_awaited_once_with(72, QolsysHvacMode.HEAT)
