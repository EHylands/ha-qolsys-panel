from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from .errors import QolsysOperationTimeoutError, QolsysUserCodeError, QolsysZoneBypassError

from .enum_qolsys import (
    PartitionAlarmState,
    PartitionAlarmType,
    PartitionArmingType,
    PartitionError,
    PartitionQuickExitState,
    PartitionSystemStatus,
    QolsysNotification,
)
from .observable import Event, QolsysObservable

if TYPE_CHECKING:
    from .controller import QolsysController

LOGGER = logging.getLogger(__name__)


class QolsysPartition(QolsysObservable):
    EXIT_SOUNDS_ARRAY = ["ON", "OFF", ""]  # noqa: RUF012
    ENTRY_DELAYS_ARRAY = ["ON", "OFF", ""]  # noqa: RUF012

    def __init__(
        self,
        controller: QolsysController,
        partition_dict: dict[str, str],
        settings_dict: dict[str, str],
        alarm_state: PartitionAlarmState,
        alarm_type_array: list[PartitionAlarmType],
        quick_exit_state: PartitionQuickExitState,
    ) -> None:
        super().__init__()

        self._controller: QolsysController = controller

        # Partition info (partition table)
        self._id: str = partition_dict.get("partition_id", "")
        self._name: str = partition_dict.get("name", "")
        self._devices = partition_dict.get("devices", "")
        self._last_error: PartitionError = PartitionError.NONE
        self._last_error_at: datetime | None = None
        self._open_zones: list[int] = []

        # Partition Settings (qolsyssettings table)
        self._system_status: PartitionSystemStatus = PartitionSystemStatus(settings_dict.get("SYSTEM_STATUS", ""))
        self._system_status_changed_time: str = settings_dict.get("SYSTEM_STATUS_CHANGED_TIME", "")
        self._exit_sounds: str = settings_dict.get("EXIT_SOUNDS", "")
        self._entry_delays: str = settings_dict.get("ENTRY_DELAYS", "")

        # Alarm State (state table)
        self._alarm_state: PartitionAlarmState = alarm_state
        self._delay_reset: bool = False
        self._delay_task: asyncio.Task[None] | None = None

        # Alarm Type (alarmedsensor table)
        self._alarm_type_array: list[PartitionAlarmType] = []
        self.append_alarm_type(alarm_type_array)

        # Quick Exit State
        self._quick_exit_state: PartitionQuickExitState = quick_exit_state
        self._quick_exit_delay: int = 0
        self._quick_exit_start_time: int = 0

        # Other
        self._command_exit_sounds: bool = True
        self._command_arm_stay_instant: bool = True
        self._command_arm_stay_silent_disarming: bool = False
        self._command_arm_entry_delay: bool = True

    def update_partition(self, data: dict[str, str]) -> None:
        # Check if we are updating same partition_id
        partition_id_update = data.get("partition_id", "")
        if partition_id_update != self.id:
            LOGGER.error(
                "Updating Partition%s (%s) with Partition '%s' (different id)", self._id, self._name, partition_id_update
            )
            return

        self.start_batch_update()

        # Update Partition Name
        if "name" in data:
            self.name = data.get("name", "")

        # Update Partition Devices
        if "devices" in data:
            self._devices = data.get("devices", "")

        self.end_batch_update()

    def update_settings(self, data: dict[str, str]) -> None:
        self.start_batch_update()

        # Update system_status
        if "SYSTEM_STATUS" in data:
            status_raw = data.get("SYSTEM_STATUS", "")
            try:
                self.system_status = PartitionSystemStatus(status_raw)
            except ValueError:
                LOGGER.error("Partition%s (%s) - unknown SYSTEM_STATUS: %s", self._id, self._name, status_raw)
                self.system_status = PartitionSystemStatus.UNKNOWN

        # Update system_status_changed_time
        if "SYSTEM_STATUS_CHANGED_TIME" in data:
            self.system_status_changed_time = data.get("SYSTEM_STATUS_CHANGED_TIME", "")

        # Update exit_sounds
        if "EXIT_SOUNDS" in data:
            self.exit_sounds = data.get("EXIT_SOUNDS", "")

        # Update entry_delays
        if "ENTRY_DELAYS" in data:
            self.entry_delays = data.get("ENTRY_DELAYS", "")

        self.end_batch_update()

    def to_dict_partition(self) -> dict[str, str]:
        return {
            "partition_id": self.id,
            "name": self.name,
            "devices": self._devices,
        }

    def to_dict_settings(self) -> dict[str, str]:
        return {
            "SYSTEM_STATUS": self.system_status.value,
            "SYSTEM_STATUS_CHANGED_TIME": self.system_status_changed_time,
            "EXIT_SOUNDS": self._exit_sounds,
            "ENTRY_DELAYS": self._entry_delays,
        }

    # -----------------------------
    # command methods
    # -----------------------------

    async def arm(self, arming_type: PartitionArmingType, user_code: str = "") -> None:
        try:
            self.last_error = PartitionError.NONE

            await self._controller.commands.panel.arm(
                self.id,
                arming_type,
                user_code,
                self.command_exit_sounds,
                self.command_arm_stay_instant,
                self.command_arm_entry_delay,
            )

        except QolsysUserCodeError as err:
            LOGGER.debug("MQTT: arm command error - user_code error")
            self.last_error = PartitionError.USER_CODE_ERROR
            raise err

        except QolsysZoneBypassError as err:
            LOGGER.debug("MQTT: arm command error - open zones preventing arming: %s", err.zones)
            self.last_error = PartitionError.ZONE_BYPASS_ERROR
            raise err

        except QolsysOperationTimeoutError as err:
            LOGGER.debug("MQTT: arm command error - operation timed out")
            self.last_error = PartitionError.PANEL_TIMEOUT
            raise err

    async def disarm(self, user_code: str = "") -> None:
        try:
            self.last_error = PartitionError.NONE
            await self._controller.commands.panel.disarm(self.id, user_code, self.command_arm_stay_silent_disarming)

        except QolsysUserCodeError as err:
            LOGGER.debug("MQTT: disarm command error - user_code error")
            self.last_error = PartitionError.USER_CODE_ERROR
            raise err

        except QolsysOperationTimeoutError as err:
            LOGGER.debug("MQTT: disarm command error - operation timed out")
            self.last_error = PartitionError.PANEL_TIMEOUT
            raise err

    # -----------------------------
    # properties + setters
    # -----------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if self._name != value:
            LOGGER.debug("Partition%s (%s) - name: %s", self._id, self._name, value)
            self._name = value
            self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

    @property
    def system_status(self) -> PartitionSystemStatus:
        return self._system_status

    @system_status.setter
    def system_status(self, new_value: PartitionSystemStatus) -> None:
        if self._system_status != new_value:
            LOGGER.debug("Partition%s (%s) - system_status: %s", self.id, self.name, new_value)
            self._system_status = new_value

            # If delay task is running, cancel it since system_status has changed
            if self._delay_task and not self._delay_task.done():
                self._delay_task.cancel()
                self._delay_task = None

            self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

    @property
    def system_status_changed_time(self) -> str:
        return self._system_status_changed_time

    @system_status_changed_time.setter
    def system_status_changed_time(self, value: str) -> None:
        if self._system_status_changed_time != value:
            LOGGER.debug("Partition%s (%s) - system_status_changed_time: %s", self._id, self._name, value)
            self._system_status_changed_time = value
            self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

    @property
    def alarm_state(self) -> PartitionAlarmState:
        return self._alarm_state

    @alarm_state.setter
    def alarm_state(self, new_value: PartitionAlarmState) -> None:
        if self._alarm_state != new_value:
            # Need to delay DELAY -> NONE transition to allow for the panel to update system_status first
            if self.alarm_state == PartitionAlarmState.DELAY and new_value == PartitionAlarmState.NONE:
                LOGGER.debug("Partition%s (%s) - alarm_state: Dectected DELAY reset to NONE", self.id, self.name)
                self._delay_reset = True

                async def _delayed_notify() -> None:
                    await asyncio.sleep(3)
                    LOGGER.debug("Partition%s (%s) - alarm_state: %s", self.id, self.name, new_value)
                    self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

                if self._delay_task and not self._delay_task.done():
                    self._delay_task.cancel()
                    self._delay_task = None
                self._alarm_state = new_value
                self._delay_task = asyncio.create_task(_delayed_notify())
                return

            LOGGER.debug("Partition%s (%s) - alarm_state: %s", self.id, self.name, new_value)
            self._alarm_state = new_value
            self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

    @property
    def alarm_type_array(self) -> list[PartitionAlarmType]:
        return self._alarm_type_array

    @alarm_type_array.setter
    def alarm_type_array(self, new_alarm_type_array: list[PartitionAlarmType]) -> None:
        # If no changes are detected: return without notification
        if sorted(new_alarm_type_array, key=lambda c: c.value) == sorted(self.alarm_type_array, key=lambda c: c.value):
            return

        # alarm_type_array are different:
        self._alarm_type_array = []

        # If all alarm have been cleared
        if new_alarm_type_array == []:
            LOGGER.debug("Partition%s (%s) - alarm_type: %s", self._id, self._name, "None")
            self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))
            return

        self.append_alarm_type(new_alarm_type_array)

    @property
    def exit_sounds(self) -> bool:
        return self._exit_sounds.lower() == "on"

    @exit_sounds.setter
    def exit_sounds(self, value: str) -> None:
        if value not in self.EXIT_SOUNDS_ARRAY:
            LOGGER.debug("Partition%s (%s) - Unknow exit_sounds %s", self._id, self._name, value)
            return

        if self._exit_sounds != value:
            LOGGER.debug("Partition%s (%s) - exit_sound: %s", self._id, self._name, value)
            self._exit_sounds = value
            self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

    @property
    def entry_delays(self) -> bool:
        return self._entry_delays.lower() == "on"

    @entry_delays.setter
    def entry_delays(self, value: str) -> None:
        if value not in self.ENTRY_DELAYS_ARRAY:
            LOGGER.debug("Partition%s (%s) - Unknow entry_delays %s", self._id, self._name, value)
            return

        if self._entry_delays != value:
            LOGGER.debug("Partition%s (%s) - entry_delays: %s", self._id, self._name, value)
            self._entry_delays = value
            self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

    @property
    def quick_exit_active(self) -> bool:
        return self._quick_exit_state == "Started"

    @property
    def quick_exit_state(self) -> PartitionQuickExitState:
        return self._quick_exit_state

    @quick_exit_state.setter
    def quick_exit_state(self, value: PartitionQuickExitState) -> None:
        if self._quick_exit_state != value:
            LOGGER.debug("Partition%s (%s) - quick_exit_state: %s", self._id, self._name, value)
            self._quick_exit_state = value
            self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

    @property
    def quick_exit_delay(self) -> int:
        return self._quick_exit_delay

    @quick_exit_delay.setter
    def quick_exit_delay(self, value: int) -> None:
        if self._quick_exit_delay != value:
            LOGGER.debug("Partition%s (%s) - quick_exit_delay: %s", self._id, self._name, value)
            self._quick_exit_delay = value
            self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

    @property
    def quick_exit_start_time(self) -> int:
        return self._quick_exit_start_time

    @quick_exit_start_time.setter
    def quick_exit_start_time(self, value: int) -> None:
        if self._quick_exit_start_time != value:
            LOGGER.debug("Partition%s (%s) - quick_exit_start_time: %s", self._id, self._name, value)
            self._quick_exit_start_time = value
            self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

    @property
    def command_exit_sounds(self) -> bool:
        return self._command_exit_sounds

    @command_exit_sounds.setter
    def command_exit_sounds(self, value: bool) -> None:
        self._command_exit_sounds = value
        LOGGER.debug("Partition%s (%s) - command_exit_sounds: %s", self._id, self._name, value)
        self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

    @property
    def command_arm_stay_instant(self) -> bool:
        return self._command_arm_stay_instant

    @command_arm_stay_instant.setter
    def command_arm_stay_instant(self, value: bool) -> None:
        self._command_arm_stay_instant = value
        LOGGER.debug("Partition%s (%s) - arm_stay_instant: %s", self._id, self._name, value)
        self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

    @property
    def command_arm_stay_silent_disarming(self) -> bool:
        return self._command_arm_stay_silent_disarming

    @command_arm_stay_silent_disarming.setter
    def command_arm_stay_silent_disarming(self, value: bool) -> None:
        self._command_arm_stay_silent_disarming = value
        LOGGER.debug("Partition%s (%s) - arm_stay_silent_disarming: %s", self._id, self._name, value)
        self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

    @property
    def command_arm_entry_delay(self) -> bool:
        return self._command_arm_entry_delay

    @command_arm_entry_delay.setter
    def command_arm_entry_delay(self, value: bool) -> None:
        self._command_arm_entry_delay = value
        LOGGER.debug("Partition%s (%s) - command_arm_entry_delay: %s", self._id, self._name, value)
        self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

    @property
    def open_zones(self) -> list[int]:
        return self._open_zones

    @property
    def last_error(self) -> PartitionError:
        return self._last_error

    @last_error.setter
    def last_error(self, value: PartitionError) -> None:
        if self._last_error != value:
            LOGGER.debug("Partition%s (%s) - last_error: %s", self._id, self._name, value)
            self._last_error = value
            if value != PartitionError.NONE:
                self.last_error_at = datetime.now(timezone.utc)
            else:
                self.last_error_at = None
            self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

    @property
    def last_error_at(self) -> datetime | None:
        return self._last_error_at

    @last_error_at.setter
    def last_error_at(self, value: datetime | None) -> None:
        if self._last_error_at != value:
            LOGGER.debug("Partition%s (%s) - last_error_at: %s", self._id, self._name, value)
            self._last_error_at = value
            self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))

    def append_alarm_type(self, new_alarm_type_array: list[PartitionAlarmType]) -> None:
        data_changed = False

        for new_alarm_type in new_alarm_type_array:
            # Map values to Police Emergency if needed
            if new_alarm_type in {
                PartitionAlarmType.GLASS_BREAK,
                PartitionAlarmType.GLASS_BREAK_AWAY_ONLY,
                PartitionAlarmType.ENTRY_EXIT_LONG_DELAY,
                PartitionAlarmType.ENTRY_EXIT_NORMAL_DELAY,
                PartitionAlarmType.INSTANT_PERIMETER_DW,
                PartitionAlarmType.INSTANT_INTERIOR_DOOR,
                PartitionAlarmType.AWAY_DELAY_MOTION,
                PartitionAlarmType.AWAY_INSTANT_MOTION,
                PartitionAlarmType.REPORTING_SAFETY_SENSOR,
                PartitionAlarmType.DELAYED_REPORTING_SAFETY_SENSOR,
                PartitionAlarmType.AWAY_INSTANT_FOLLOWER_DELAY,
                PartitionAlarmType.STAY_INSTANT_MOTION,
                PartitionAlarmType.STAY_DELAY_MOTION,
                PartitionAlarmType.SHOCK,
                PartitionAlarmType.EMPTY,
            }:
                new_alarm_type = PartitionAlarmType.POLICE_EMERGENCY

            # Map values to Fire Emergency if needed
            if new_alarm_type in {
                PartitionAlarmType.SMOKE_HEAT,
            }:
                new_alarm_type = PartitionAlarmType.FIRE_EMERGENCY

            # Value already in array
            if new_alarm_type in self._alarm_type_array:
                continue

            self._alarm_type_array.append(new_alarm_type)
            data_changed = True

        if data_changed:
            self.notify(Event(QolsysNotification.PARTITION_UPDATE, self, self.to_dict_event()))
            for alarm in self._alarm_type_array:
                LOGGER.debug("Partition%s (%s) - alarm_type: %s", self._id, self._name, alarm)

    def to_dict_event(self) -> dict[str, Any]:
        partition_id = 0
        status_changed_time = 0

        try:
            partition_id = int(self.id)
        except (ValueError, TypeError):
            LOGGER.debug("Partition%s (%s) - invalid id in event payload: %s", self._id, self._name, self.id)

        try:
            status_time_parts = self.system_status_changed_time.split(",")
            status_changed_time = int(status_time_parts[1] if len(status_time_parts) > 1 else status_time_parts[0])
        except (ValueError, TypeError, IndexError):
            LOGGER.debug(
                "Partition%s (%s) - invalid SYSTEM_STATUS_CHANGED_TIME in event payload: %s",
                self._id,
                self._name,
                self.system_status_changed_time,
            )

        return {
            "id": partition_id,
            "type": "partition",
            "state": {
                "status": self.system_status.name.lower(),
                "alarm_state": self.alarm_state.name.lower(),
                "alarm_array": [alarm_type.name.lower() for alarm_type in self.alarm_type_array],
                "status_changed_time": datetime.fromtimestamp(status_changed_time / 1000, tz=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "entry_delays": self.entry_delays,
                "exit_sounds": self.exit_sounds,
                "quick_exit_state": self.quick_exit_state.value,
                "quick_exit_delay": self.quick_exit_delay,
                "quick_exit_start_time": self.quick_exit_start_time,
                "last_error": self.last_error.value,
                "last_error_at": self.last_error_at.isoformat().replace("+00:00", "Z") if self.last_error_at else None,
            },
            "attributes": {
                "name": self.name,
            },
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "version": 1,
        }
