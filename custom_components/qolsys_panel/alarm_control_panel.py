"""Support for Qolsys Panel Partition."""

from __future__ import annotations

import logging

from qolsys_controller import qolsys_controller
from qolsys_controller.enum_qolsys import (
    PartitionAlarmState,
    PartitionArmingType,
    PartitionSystemStatus,
)
from qolsys_controller.errors import (
    QolsysOperationTimeoutError,
    QolsysUserCodeError,
    QolsysZoneBypassError,
)

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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

    entities: list[AlarmControlPanelEntity] = []

    for partition in QolsysPanel.state.partitions:
        entities.append(
            PartitionAlarmControlPanel(
                QolsysPanel,
                partition.id,
                config_entry.unique_id,
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
        self._attr_code_arm_required = QolsysPanel.settings.check_user_code_on_arm
        if QolsysPanel.settings.check_user_code_on_arm:
            self._attr_code_format = CodeFormat.NUMBER

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
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
        try:
            await self._partition.disarm(user_code=code)
        except QolsysUserCodeError as err:
            raise HomeAssistantError("DISARM: Invalid user code") from err
        except QolsysOperationTimeoutError as err:
            raise HomeAssistantError("DISARM: Operation timed out") from err
        except Exception as err:
            _LOGGER.error("Failed to disarm partition%s: %s", self._partition_id, err)
            raise HomeAssistantError("DISARM: Failed to disarm partition") from err

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send ARM-STAY command."""
        self._async_alarm_arm_custom(PartitionArmingType.ARM_STAY, code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send ARM-AWAY command."""
        self._async_alarm_arm_custom(PartitionArmingType.ARM_AWAY, code)

    async def async_alarm_arm_night(self, code=None):
        """Send ARM-NIGHT command."""
        self._async_alarm_arm_custom(PartitionArmingType.ARM_NIGHT, code)

    async def _async_alarm_arm_custom(
        self, arm_mode: PartitionArmingType, code: str | None = None
    ) -> None:
        """Arm with custom mode."""
        try:
            await self._partition.arm(arm_mode, user_code=code)
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
