"""Support for Qolsys Panel Partition Control."""

from __future__ import annotations

import logging

from qolsys_controller import qolsys_controller
from qolsys_controller.enum import (
    PartitionAlarmState,
    PartitionSystemStatus,
    PartitionArmingType,
)
from qolsys_controller.errors import QolsysUserCodeError

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.exceptions import HomeAssistantError


from .entity import QolsysPartitionEntity
from .types import QolsysPanelConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up alarm control panels for each partition."""
    QolsysPanel = config_entry.runtime_data

    async_add_entities(
        PartitionAlarmControlPanel(
            QolsysPanel,
            partition.id,
            config_entry.unique_id,
        )
        for partition in QolsysPanel.state.partitions
    )


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
        """Initialise a Qolsys Alarm control panel entity."""
        super().__init__(QolsysPanel, partition_id, unique_id)
        self._attr_unique_id = self._partition_unique_id
        self._attr_code_arm_required = QolsysPanel.settings.check_user_code_on_arm
        if QolsysPanel.settings.check_user_code_on_arm:
            self._attr_code_format = CodeFormat.NUMBER

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the alarm."""

        alarm_state = self._partition.alarm_state
        system_status = self._partition.system_status

        if alarm_state == PartitionAlarmState.ALARM:
            return AlarmControlPanelState.TRIGGERED

        if (
            system_status == PartitionSystemStatus.DISARM
            and alarm_state != PartitionAlarmState.ALARM
        ):
            return AlarmControlPanelState.DISARMED

        if system_status in (
            PartitionSystemStatus.ARM_AWAY_EXIT_DELAY,
            PartitionSystemStatus.ARM_STAY_EXIT_DELAY,
            PartitionSystemStatus.ARM_NIGHT_EXIT_DELAY,
        ):
            return AlarmControlPanelState.ARMING

        if system_status == PartitionSystemStatus.ARM_STAY:
            return AlarmControlPanelState.ARMED_HOME

        if system_status == PartitionSystemStatus.ARM_AWAY:
            return AlarmControlPanelState.ARMED_AWAY

        if system_status == PartitionSystemStatus.ARM_NIGHT:
            return AlarmControlPanelState.ARMED_NIGHT

        return None

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm this panel."""
        silent_disarming = self._partition.command_arm_stay_silent_disarming

        try:
            await self.QolsysPanel.command_disarm(
                self._partition_id, user_code=code, silent_disarming=silent_disarming
            )
        except QolsysUserCodeError as err:
            _LOGGER.error(
                "Failed to disarm partition%s due to invalid user code",
                self._partition_id,
            )
            raise HomeAssistantError("DISARM: Invalid user code") from err

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send ARM-STAY command."""
        exit_sounds = self._partition.command_exit_sounds
        arm_stay_instant = self._partition.command_arm_stay_instant
        entry_delay = self._partition.command_arm_entry_delay

        try:
            await self.QolsysPanel.command_arm(
                partition_id=self._partition_id,
                arming_type=PartitionArmingType.ARM_STAY,
                user_code=code,
                exit_sounds=exit_sounds,
                instant_arm=arm_stay_instant,
                entry_delay=entry_delay,
            )
        except QolsysUserCodeError as err:
            _LOGGER.error(
                "Failed to arm partition%s due to invalid user code",
                self._partition_id,
            )
            raise HomeAssistantError("ARM HOME: Invalid user code") from err

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send ARM-AWAY command."""
        exit_sounds = self._partition.command_exit_sounds
        arm_stay_instant = self._partition.command_arm_stay_instant
        entry_delay = self._partition.command_arm_entry_delay

        try:
            await self.QolsysPanel.command_arm(
                self._partition_id,
                arming_type=PartitionArmingType.ARM_AWAY,
                user_code=code,
                exit_sounds=exit_sounds,
                instant_arm=arm_stay_instant,
                entry_delay=entry_delay,
            )
        except QolsysUserCodeError as err:
            _LOGGER.error(
                "Failed to arm partition%s due to invalid user code",
                self._partition_id,
            )
            raise HomeAssistantError("ARM AWAY: Invalid user code") from err

    async def async_alarm_arm_night(self, code=None):
        """Send ARM-NIGHT command."""
        exit_sounds = self._partition.command_exit_sounds
        arm_stay_instant = self._partition.command_arm_stay_instant
        entry_delay = self._partition.command_arm_entry_delay

        try:
            await self.QolsysPanel.command_arm(
                self._partition_id,
                arming_type=PartitionArmingType.ARM_NIGHT,
                user_code=code,
                exit_sounds=exit_sounds,
                instant_arm=arm_stay_instant,
                entry_delay=entry_delay,
            )
        except QolsysUserCodeError as err:
            _LOGGER.error(
                "Failed to arm partition%s due to invalid user code",
                self._partition_id,
            )
            raise HomeAssistantError("ARM NIGHT: Invalid user code") from err
