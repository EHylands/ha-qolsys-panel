"""Support for Qolsys Panel Partition."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysPartitionEntity
from .types import QolsysPanelConfigEntry
from .vendor.qolsys_controller import qolsys_controller
from .vendor.qolsys_controller.enum_qolsys import (
    PartitionAlarmState,
    PartitionArmingType,
    PartitionSystemStatus,
)
from .vendor.qolsys_controller.errors import (
    QolsysOperationTimeoutError,
    QolsysUserCodeError,
    QolsysZoneBypassError,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up alarm control panels for each partition."""
    QolsysPanel = config_entry.runtime_data
    if (unique_id := config_entry.unique_id) is None:
        # A forwarded platform must not raise ConfigEntryNotReady: HA logs a
        # complaint rather than retrying, and __init__.async_setup_entry already
        # refuses a None unique_id before any platform is set up (review N5).
        raise ValueError("Config entry has no unique_id; re-add the integration")

    entities: list[AlarmControlPanelEntity] = []

    for partition in QolsysPanel.state.partitions:
        entities.append(
            PartitionAlarmControlPanel(
                QolsysPanel,
                partition.id,
                unique_id,
            )
        )

    async_add_entities(entities)


class PartitionAlarmControlPanel(QolsysPartitionEntity, AlarmControlPanelEntity):
    """An alarm control panel entity for a Qolsys Panel."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )

    def __init__(
        self, QolsysPanel: qolsys_controller, partition_id: str, unique_id: str
    ) -> None:
        super().__init__(QolsysPanel, partition_id, unique_id)
        self._attr_unique_id = self._partition_unique_id

    @property
    def _next_action_is_arm(self) -> bool:
        """Return whether the next state change is arming.

        A triggered alarm can report a DISARM system status; disarming is
        still the pending action in that case.
        """
        return (
            self._partition.system_status == PartitionSystemStatus.DISARM
            and self._partition.alarm_state != PartitionAlarmState.ALARM
        )

    @property
    def code_arm_required(self) -> bool:
        """Return whether a code is required for the next state change."""
        if self._next_action_is_arm:
            return self.QolsysPanel.settings.check_user_code_on_arm
        return self.QolsysPanel.settings.check_user_code_on_disarm

    @property
    def code_format(self) -> CodeFormat | None:
        """Return the code format when the next state change requires a code."""

        # Disarm prompts whenever code_format is set, so the format must be
        # exposed only when the pending action actually needs a code.
        return CodeFormat.NUMBER if self.code_arm_required else None

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        alarm_state = self._partition.alarm_state
        system_status = self._partition.system_status

        if alarm_state == PartitionAlarmState.ALARM:
            return AlarmControlPanelState.TRIGGERED

        if system_status == PartitionSystemStatus.DISARM:
            return AlarmControlPanelState.DISARMED

        if system_status in (
            PartitionSystemStatus.ARM_AWAY_EXIT_DELAY,
            PartitionSystemStatus.ARM_STAY_EXIT_DELAY,
            PartitionSystemStatus.ARM_NIGHT_EXIT_DELAY,
        ):
            return AlarmControlPanelState.ARMING

        if alarm_state == PartitionAlarmState.DELAY:
            return AlarmControlPanelState.PENDING

        if system_status == PartitionSystemStatus.ARM_STAY:
            return AlarmControlPanelState.ARMED_HOME

        if system_status == PartitionSystemStatus.ARM_AWAY:
            return AlarmControlPanelState.ARMED_AWAY

        if system_status == PartitionSystemStatus.ARM_NIGHT:
            return AlarmControlPanelState.ARMED_NIGHT

        return None

    async def _validate_user_code(self, code: str | None, action: str) -> None:
        """Reject a missing or unknown user code before any command is sent.

        The panel disarms on the authority of the paired keypad certificate and
        never checks a user code itself, so this check is the only one there is
        (audit C1). The comparison runs in constant time against the stored
        hash of the code (see the vendored panel.check_user, audit H3/L5).
        """
        if not code:
            raise ServiceValidationError(f"{action}: A user code is required")

        # check_user derives a PBKDF2 hash per stored code (audit H3), so it runs
        # in an executor rather than on the event loop.
        user_id = await asyncio.to_thread(self.QolsysPanel.panel.check_user, code)
        if user_id == -1:
            raise ServiceValidationError(f"{action}: Invalid user code")

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm this panel."""
        if self.QolsysPanel.settings.check_user_code_on_disarm:
            await self._validate_user_code(code, "DISARM")

        try:
            await self._partition.disarm(user_code=code or "")
        except QolsysUserCodeError as err:
            raise HomeAssistantError("DISARM: Invalid user code") from err
        except QolsysOperationTimeoutError as err:
            raise HomeAssistantError("DISARM: Operation timed out") from err
        except Exception as err:
            _LOGGER.error("Failed to disarm partition%s: %s", self._partition_id, err)
            raise HomeAssistantError("DISARM: Failed to disarm partition") from err

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send ARM-STAY command."""
        await self._async_alarm_arm_custom(PartitionArmingType.ARM_STAY, code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send ARM-AWAY command."""
        await self._async_alarm_arm_custom(PartitionArmingType.ARM_AWAY, code)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send ARM-NIGHT command."""
        await self._async_alarm_arm_custom(PartitionArmingType.ARM_NIGHT, code)

    async def _async_alarm_arm_custom(
        self, arm_mode: PartitionArmingType, code: str | None = None
    ) -> None:
        """Arm with custom mode."""
        if self.QolsysPanel.settings.check_user_code_on_arm:
            await self._validate_user_code(code, arm_mode.name)

        try:
            await self._partition.arm(arm_mode, user_code=code or "")
        except QolsysUserCodeError as err:
            raise HomeAssistantError(f"{arm_mode.name}: Invalid user code") from err
        except QolsysOperationTimeoutError as err:
            raise HomeAssistantError(f"{arm_mode.name}: Operation timed out") from err
        except QolsysZoneBypassError as err:
            raise HomeAssistantError(
                f"{arm_mode.name}: Zone bypass required:{err.zones}"
            ) from err
        except Exception as err:
            _LOGGER.error("Failed to arm partition%s: %s", self._partition_id, err)
            raise HomeAssistantError(
                f"{arm_mode.name}: Failed to arm partition"
            ) from err
