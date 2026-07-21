"""Tests for the Qolsys Panel switches."""

from unittest.mock import AsyncMock, MagicMock

from conftest import PANEL_MAC
import pytest

from custom_components.qolsys_panel.switch import (
    AutomationDevice_Outlet,
    PartitionSwitch_ArmStayInstant,
    PartitionSwitch_EntryDelay,
    PartitionSwitch_ExitSounds,
    PartitionSwitch_SilentDisarming,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant

UID = PANEL_MAC

# (switch class, the partition command attribute it drives)
PARTITION_SWITCHES = [
    (PartitionSwitch_ExitSounds, "command_exit_sounds"),
    (PartitionSwitch_EntryDelay, "command_arm_entry_delay"),
    (PartitionSwitch_ArmStayInstant, "command_arm_stay_instant"),
    (PartitionSwitch_SilentDisarming, "command_arm_stay_silent_disarming"),
]


@pytest.fixture
def controller() -> MagicMock:
    """A controller mock with one partition and one outlet device."""
    c = MagicMock()

    partition = MagicMock()
    partition.id = "1"
    c.state.partitions = [partition]

    service = MagicMock()
    service.endpoint = 0
    device = MagicMock()
    device.virtual_node_id = "5"
    device.service_get_protocol.return_value = [service]
    c.state.automation_devices = [device]

    return c


async def test_async_setup_entry_creates_entities(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup builds the four partition switches plus one outlet."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 5
    assert {type(e).__name__ for e in entities} == {
        "PartitionSwitch_ExitSounds",
        "PartitionSwitch_EntryDelay",
        "PartitionSwitch_ArmStayInstant",
        "PartitionSwitch_SilentDisarming",
        "AutomationDevice_Outlet",
    }


@pytest.mark.parametrize(("switch_cls", "attr"), PARTITION_SWITCHES)
def test_partition_switch_is_on(controller: MagicMock, switch_cls, attr) -> None:
    """Each partition switch reflects its partition command flag."""
    switch = switch_cls(controller, "1", UID)
    setattr(switch._partition, attr, True)
    assert switch.is_on is True
    setattr(switch._partition, attr, False)
    assert switch.is_on is False


@pytest.mark.parametrize(("switch_cls", "attr"), PARTITION_SWITCHES)
def test_partition_switch_turn_on_off(controller: MagicMock, switch_cls, attr) -> None:
    """Turning a partition switch on/off writes the partition command flag."""
    switch = switch_cls(controller, "1", UID)

    switch.turn_on()
    assert getattr(switch._partition, attr) is True

    switch.turn_off()
    assert getattr(switch._partition, attr) is False


@pytest.mark.parametrize(("switch_cls", "attr"), PARTITION_SWITCHES)
async def test_partition_switch_restore_on(
    controller: MagicMock, switch_cls, attr
) -> None:
    """Restoring an 'on' state sets the partition command flag true."""
    switch = switch_cls(controller, "1", UID)
    switch.async_get_last_state = AsyncMock(return_value=MagicMock(state="on"))

    await switch.async_added_to_hass()

    assert getattr(switch._partition, attr) is True


@pytest.mark.parametrize(("switch_cls", "attr"), PARTITION_SWITCHES)
async def test_partition_switch_restore_off(
    controller: MagicMock, switch_cls, attr
) -> None:
    """No restore state leaves the partition command flag false."""
    switch = switch_cls(controller, "1", UID)
    switch.async_get_last_state = AsyncMock(return_value=None)

    await switch.async_added_to_hass()

    assert getattr(switch._partition, attr) is False


def test_outlet_is_on(controller: MagicMock) -> None:
    """The outlet switch reflects the service on state."""
    outlet = AutomationDevice_Outlet(controller, "5", 0, UID)
    outlet._service.is_on = True
    assert outlet.is_on is True
    outlet._service.is_on = False
    assert outlet.is_on is False


async def test_outlet_turn_on_off(controller: MagicMock) -> None:
    """Turning the outlet on/off calls the service."""
    outlet = AutomationDevice_Outlet(controller, "5", 0, UID)
    outlet._service.turn_on = AsyncMock()
    outlet._service.turn_off = AsyncMock()

    await outlet.async_turn_on()
    outlet._service.turn_on.assert_awaited_once()

    await outlet.async_turn_off()
    outlet._service.turn_off.assert_awaited_once()
