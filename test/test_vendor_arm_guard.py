"""Arming refuses to proceed with an open safety zone (audit L1)."""

from unittest.mock import MagicMock

import pytest

from custom_components.qolsys_panel.vendor.qolsys_controller.commands.panel import (
    PanelCommands,
)
from custom_components.qolsys_panel.vendor.qolsys_controller.enum_qolsys import (
    PartitionArmingType,
    TroubleZoneStatus,
)
from custom_components.qolsys_panel.vendor.qolsys_controller.errors import (
    QolsysZoneBypassError,
)


def _zone(*, safety: bool, bypassable: bool) -> MagicMock:
    """An open zone in partition 1."""
    zone = MagicMock()
    zone.partition_id = "1"
    zone.sensorstatus = TroubleZoneStatus[0]
    zone.is_bypassable.return_value = bypassable
    zone.is_safety.return_value = safety
    zone.zone_id = "4"
    return zone


@pytest.fixture
def commands() -> PanelCommands:
    """A panel command service with one partition and no zones."""
    controller = MagicMock()
    controller.state.zones = []
    controller.settings.check_user_code_on_arm = False
    controller.panel.AUTO_BYPASS = "true"
    return PanelCommands(controller)


async def test_arm_refuses_an_open_safety_zone(commands: PanelCommands) -> None:
    """An open smoke, CO or water sensor stops arming (audit L1)."""
    commands._controller.state.zones = [_zone(safety=True, bypassable=False)]

    with pytest.raises(QolsysZoneBypassError) as err:
        await commands.arm("1", PartitionArmingType.ARM_AWAY)

    assert err.value.zones == ["4"]


async def test_arm_refuses_open_zones_when_auto_bypass_is_off(
    commands: PanelCommands,
) -> None:
    """The neighbouring auto-bypass guard still behaves the same way."""
    commands._controller.panel.AUTO_BYPASS = "false"
    commands._controller.state.zones = [_zone(safety=False, bypassable=True)]

    with pytest.raises(QolsysZoneBypassError):
        await commands.arm("1", PartitionArmingType.ARM_AWAY)
