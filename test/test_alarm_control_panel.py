"""Tests for the Qolsys Panel alarm control panel."""

from typing import cast
from unittest.mock import AsyncMock, MagicMock

from conftest import PANEL_MAC
import pytest

from custom_components.qolsys_panel.alarm_control_panel import (
    PartitionAlarmControlPanel,
    async_setup_entry,
)
from custom_components.qolsys_panel.const import DEFAULT_DISARM_CODE_REQUIRED
from custom_components.qolsys_panel.vendor.qolsys_controller.enum_qolsys import (
    PartitionAlarmState,
    PartitionArmingType,
    PartitionSystemStatus,
)
from custom_components.qolsys_panel.vendor.qolsys_controller.errors import (
    QolsysOperationTimeoutError,
    QolsysUserCodeError,
    QolsysZoneBypassError,
)
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

UID = PANEL_MAC


@pytest.fixture
def controller() -> MagicMock:
    """A controller mock with one partition."""
    c = MagicMock()
    partition = MagicMock()
    partition.id = "1"
    c.state.partitions = [partition]
    return c


def _panel(controller: MagicMock) -> PartitionAlarmControlPanel:
    """Build the alarm entity with awaitable partition commands."""
    entity = PartitionAlarmControlPanel(controller, "1", UID)
    entity._partition.arm = AsyncMock()
    entity._partition.disarm = AsyncMock()
    return entity


async def test_async_setup_entry_creates_entities(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup builds one alarm control panel per partition."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], PartitionAlarmControlPanel)


@pytest.mark.parametrize(
    ("alarm_state", "system_status", "expected"),
    [
        (
            PartitionAlarmState.ALARM,
            PartitionSystemStatus.ARM_AWAY,
            AlarmControlPanelState.TRIGGERED,
        ),
        (
            PartitionAlarmState.NONE,
            PartitionSystemStatus.DISARM,
            AlarmControlPanelState.DISARMED,
        ),
        (
            PartitionAlarmState.NONE,
            PartitionSystemStatus.ARM_AWAY_EXIT_DELAY,
            AlarmControlPanelState.ARMING,
        ),
        (
            PartitionAlarmState.NONE,
            PartitionSystemStatus.ARM_STAY_EXIT_DELAY,
            AlarmControlPanelState.ARMING,
        ),
        (
            PartitionAlarmState.NONE,
            PartitionSystemStatus.ARM_NIGHT_EXIT_DELAY,
            AlarmControlPanelState.ARMING,
        ),
        (
            PartitionAlarmState.NONE,
            PartitionSystemStatus.ARM_STAY,
            AlarmControlPanelState.ARMED_HOME,
        ),
        (
            PartitionAlarmState.NONE,
            PartitionSystemStatus.ARM_AWAY,
            AlarmControlPanelState.ARMED_AWAY,
        ),
        (
            PartitionAlarmState.NONE,
            PartitionSystemStatus.ARM_NIGHT,
            AlarmControlPanelState.ARMED_NIGHT,
        ),
        (PartitionAlarmState.NONE, PartitionSystemStatus.UNKNOWN, None),
    ],
)
def test_alarm_state(
    controller: MagicMock, alarm_state, system_status, expected
) -> None:
    """The alarm state maps the partition alarm/system status."""
    entity = _panel(controller)
    entity._partition.alarm_state = alarm_state
    entity._partition.system_status = system_status
    assert entity.alarm_state == expected


@pytest.mark.parametrize("required", [True, False])
def test_code_required_when_arming(controller: MagicMock, required: bool) -> None:
    """When disarmed, the arm code option drives code requirement/format."""
    entity = _panel(controller)
    entity._partition.system_status = PartitionSystemStatus.DISARM
    entity._partition.alarm_state = PartitionAlarmState.NONE
    controller.settings.check_user_code_on_arm = required

    assert entity.code_arm_required is required
    assert entity.code_format == (CodeFormat.NUMBER if required else None)


@pytest.mark.parametrize("required", [True, False])
def test_code_required_when_disarming(controller: MagicMock, required: bool) -> None:
    """When armed, the disarm code option drives code requirement/format."""
    entity = _panel(controller)
    entity._partition.system_status = PartitionSystemStatus.ARM_AWAY
    entity._partition.alarm_state = PartitionAlarmState.NONE
    controller.settings.check_user_code_on_disarm = required

    assert entity.code_arm_required is required
    assert entity.code_format == (CodeFormat.NUMBER if required else None)


async def test_disarm(controller: MagicMock) -> None:
    """Disarm forwards the code to the partition."""
    entity = _panel(controller)
    await entity.async_alarm_disarm("1234")
    cast(AsyncMock, entity._partition.disarm).assert_awaited_once_with(user_code="1234")


def test_disarm_requires_a_code_by_default() -> None:
    """A fresh install must not offer a one-click disarm (audit C1)."""
    assert DEFAULT_DISARM_CODE_REQUIRED is True


async def test_disarm_without_code_is_rejected(controller: MagicMock) -> None:
    """With the code check on, an empty code never reaches the panel (audit C1)."""
    entity = _panel(controller)
    controller.settings.check_user_code_on_disarm = True

    with pytest.raises(HomeAssistantError):
        await entity.async_alarm_disarm(None)

    cast(AsyncMock, entity._partition.disarm).assert_not_awaited()


async def test_disarm_with_unknown_code_is_rejected(controller: MagicMock) -> None:
    """An unknown code is refused by the integration, not by the panel (audit C1)."""
    entity = _panel(controller)
    controller.settings.check_user_code_on_disarm = True
    controller.panel.check_user = MagicMock(return_value=-1)

    with pytest.raises(HomeAssistantError):
        await entity.async_alarm_disarm("9999")

    controller.panel.check_user.assert_called_once_with("9999")
    cast(AsyncMock, entity._partition.disarm).assert_not_awaited()


async def test_disarm_with_valid_code_is_sent(controller: MagicMock) -> None:
    """A code the panel database knows is forwarded (audit C1)."""
    entity = _panel(controller)
    controller.settings.check_user_code_on_disarm = True
    controller.panel.check_user = MagicMock(return_value=2)

    await entity.async_alarm_disarm("1234")

    cast(AsyncMock, entity._partition.disarm).assert_awaited_once_with(user_code="1234")


async def test_arm_without_code_is_rejected_when_required(
    controller: MagicMock,
) -> None:
    """Arming with the code option on also validates before sending (audit C1)."""
    entity = _panel(controller)
    controller.settings.check_user_code_on_arm = True

    with pytest.raises(HomeAssistantError):
        await entity.async_alarm_arm_away(None)

    cast(AsyncMock, entity._partition.arm).assert_not_awaited()


@pytest.mark.parametrize(
    "error",
    [QolsysUserCodeError(), QolsysOperationTimeoutError(), RuntimeError("boom")],
)
async def test_disarm_errors(controller: MagicMock, error: Exception) -> None:
    """Disarm failures surface as HomeAssistantError."""
    entity = _panel(controller)
    cast(AsyncMock, entity._partition.disarm).side_effect = error
    with pytest.raises(HomeAssistantError):
        await entity.async_alarm_disarm("1234")


@pytest.mark.parametrize(
    ("method", "arm_mode"),
    [
        ("async_alarm_arm_home", PartitionArmingType.ARM_STAY),
        ("async_alarm_arm_away", PartitionArmingType.ARM_AWAY),
        ("async_alarm_arm_night", PartitionArmingType.ARM_NIGHT),
    ],
)
async def test_arm(controller: MagicMock, method: str, arm_mode) -> None:
    """Each arm method forwards the right arming mode and code."""
    entity = _panel(controller)
    await getattr(entity, method)("1234")
    cast(AsyncMock, entity._partition.arm).assert_awaited_once_with(
        arm_mode, user_code="1234"
    )


@pytest.mark.parametrize(
    "error",
    [
        QolsysUserCodeError(),
        QolsysOperationTimeoutError(),
        QolsysZoneBypassError(["1"]),
        RuntimeError("boom"),
    ],
)
async def test_arm_errors(controller: MagicMock, error: Exception) -> None:
    """Arm failures surface as HomeAssistantError."""
    entity = _panel(controller)
    cast(AsyncMock, entity._partition.arm).side_effect = error
    with pytest.raises(HomeAssistantError):
        await entity.async_alarm_arm_away("1234")
