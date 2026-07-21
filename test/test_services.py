"""Tests for the Qolsys Panel services."""

from unittest.mock import AsyncMock, MagicMock

from conftest import PANEL_MAC
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from qolsys_controller.errors import CommandExecutionError

from custom_components.qolsys_panel.const import (
    CONF_IMEI,
    CONF_RANDOM_MAC,
    DOMAIN,
    OPTION_TRIGGER_AUXILLIARY,
    OPTION_TRIGGER_FIRE,
    OPTION_TRIGGER_POLICE,
)
from custom_components.qolsys_panel.services import (
    async_quick_exit,
    async_trigger_auxilliary,
    async_trigger_fire,
    async_trigger_police,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

PARTITION_ID = "1"
ALL_OPTIONS_ON = {
    OPTION_TRIGGER_POLICE: True,
    OPTION_TRIGGER_AUXILLIARY: True,
    OPTION_TRIGGER_FIRE: True,
}


@pytest.fixture(autouse=True)
def _zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Mock zeroconf: the integration manifest depends on it."""


def _make_panel() -> MagicMock:
    """Return a controller mock with awaitable panel commands."""
    panel = MagicMock()
    panel.commands.panel.trigger_police = AsyncMock()
    panel.commands.panel.trigger_auxilliary = AsyncMock()
    panel.commands.panel.trigger_fire = AsyncMock()
    panel.commands.panel.quick_exit = AsyncMock()
    return panel


def _make_entry(hass: HomeAssistant, options: dict) -> MockConfigEntry:
    """Create a loaded config entry with runtime data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Qolsys Panel ({PANEL_MAC})",
        data={
            CONF_HOST: "192.168.1.50",
            CONF_MAC: PANEL_MAC,
            CONF_MODEL: "IQ Panel 4",
            CONF_IMEI: "123456789012345",
            CONF_RANDOM_MAC: "aa:bb:cc:dd:ee:01",
        },
        options=options,
        unique_id=PANEL_MAC,
    )
    entry.add_to_hass(hass)
    entry.runtime_data = _make_panel()
    entry.mock_state(hass, ConfigEntryState.LOADED)
    return entry


def _register_entity(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    """Register an alarm_control_panel entity tied to the config entry."""
    registry = er.async_get(hass)
    entity_entry = registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        f"{PANEL_MAC}_partition{PARTITION_ID}",
        config_entry=entry,
    )
    return entity_entry.entity_id


def _make_ent(entity_id: str) -> MagicMock:
    """Return a mock alarm entity as passed to the service handler."""
    ent = MagicMock()
    ent.entity_id = entity_id
    ent._partition_id = PARTITION_ID
    return ent


def _make_call(hass: HomeAssistant, data: dict) -> MagicMock:
    """Return a mock ServiceCall."""
    call = MagicMock()
    call.hass = hass
    call.data = data
    return call


async def test_trigger_police(hass: HomeAssistant) -> None:
    """Police trigger forwards partition and silent flag to the controller."""
    entry = _make_entry(hass, ALL_OPTIONS_ON)
    ent = _make_ent(_register_entity(hass, entry))

    await async_trigger_police(ent, _make_call(hass, {"silent": True}))

    entry.runtime_data.commands.panel.trigger_police.assert_awaited_once_with(
        PARTITION_ID, True
    )


async def test_trigger_auxilliary(hass: HomeAssistant) -> None:
    """Auxiliary trigger forwards partition and silent flag to the controller."""
    entry = _make_entry(hass, ALL_OPTIONS_ON)
    ent = _make_ent(_register_entity(hass, entry))

    await async_trigger_auxilliary(ent, _make_call(hass, {"silent": False}))

    entry.runtime_data.commands.panel.trigger_auxilliary.assert_awaited_once_with(
        PARTITION_ID, False
    )


async def test_trigger_fire(hass: HomeAssistant) -> None:
    """Fire trigger forwards the partition to the controller."""
    entry = _make_entry(hass, ALL_OPTIONS_ON)
    ent = _make_ent(_register_entity(hass, entry))

    await async_trigger_fire(ent, _make_call(hass, {}))

    entry.runtime_data.commands.panel.trigger_fire.assert_awaited_once_with(
        PARTITION_ID
    )


async def test_quick_exit(hass: HomeAssistant) -> None:
    """Quick exit forwards the partition and duration to the controller."""
    entry = _make_entry(hass, ALL_OPTIONS_ON)
    ent = _make_ent(_register_entity(hass, entry))

    await async_quick_exit(ent, _make_call(hass, {"duration": 45}))

    entry.runtime_data.commands.panel.quick_exit.assert_awaited_once_with(
        PARTITION_ID, 45
    )


async def test_quick_exit_command_error(hass: HomeAssistant) -> None:
    """A controller command error surfaces as a HomeAssistantError."""
    entry = _make_entry(hass, ALL_OPTIONS_ON)
    ent = _make_ent(_register_entity(hass, entry))
    entry.runtime_data.commands.panel.quick_exit.side_effect = CommandExecutionError(
        "boom"
    )

    with pytest.raises(HomeAssistantError):
        await async_quick_exit(ent, _make_call(hass, {"duration": 45}))


# (handler, call data) for every service handler.
ALL_HANDLERS = [
    (async_trigger_police, {"silent": False}),
    (async_trigger_auxilliary, {"silent": False}),
    (async_trigger_fire, {}),
    (async_quick_exit, {"duration": 30}),
]

# (handler, its option key, call data) for the handlers gated by an option.
OPTION_HANDLERS = [
    (async_trigger_police, OPTION_TRIGGER_POLICE, {"silent": False}),
    (async_trigger_auxilliary, OPTION_TRIGGER_AUXILLIARY, {"silent": False}),
    (async_trigger_fire, OPTION_TRIGGER_FIRE, {}),
]


@pytest.mark.parametrize(("handler", "data"), ALL_HANDLERS)
async def test_entity_not_registered(hass: HomeAssistant, handler, data) -> None:
    """An unknown entity raises a ValueError."""
    _make_entry(hass, ALL_OPTIONS_ON)
    ent = _make_ent("alarm_control_panel.does_not_exist")

    with pytest.raises(ValueError):
        await handler(ent, _make_call(hass, data))


@pytest.mark.parametrize(("handler", "data"), ALL_HANDLERS)
async def test_not_loaded(hass: HomeAssistant, handler, data) -> None:
    """A config entry that is not loaded raises a HomeAssistantError."""
    entry = _make_entry(hass, ALL_OPTIONS_ON)
    entry.mock_state(hass, ConfigEntryState.SETUP_ERROR)
    ent = _make_ent(_register_entity(hass, entry))

    with pytest.raises(HomeAssistantError):
        await handler(ent, _make_call(hass, data))


@pytest.mark.parametrize(("handler", "option", "data"), OPTION_HANDLERS)
async def test_option_disabled(hass: HomeAssistant, handler, option, data) -> None:
    """A trigger service refuses to run when disabled in options."""
    entry = _make_entry(hass, {option: False})
    ent = _make_ent(_register_entity(hass, entry))

    with pytest.raises(HomeAssistantError):
        await handler(ent, _make_call(hass, data))


@pytest.mark.parametrize(("handler", "data"), ALL_HANDLERS)
async def test_missing_config_entry(hass: HomeAssistant, handler, data) -> None:
    """An entity not tied to a config entry raises ServiceValidationError."""
    registry = er.async_get(hass)
    # Registered with no config entry, so config_entry_id resolves to None.
    entity_entry = registry.async_get_or_create(
        "alarm_control_panel", DOMAIN, "orphan_partition"
    )
    ent = _make_ent(entity_entry.entity_id)

    with pytest.raises(ServiceValidationError):
        await handler(ent, _make_call(hass, data))
