from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import time
from enum import StrEnum
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from ..enum_qolsys import (
    CameraServiceTransactionType,
    PartitionAlarmState,
    PartitionArmingType,
    PartitionSystemStatus,
    PhotoDirectory,
    TroubleZoneStatus,
)
from ..errors import (
    CommandExecutionError,
    QolsysInvalidPartitionIdError,
    QolsysOperationError,
    QolsysUserCodeError,
    QolsysZoneBypassError,
)
from ..mqtt_command import MQTTCommand, MQTTCommand_CameraService, MQTTCommand_Panel

if TYPE_CHECKING:
    from ..controller import QolsysController

LOGGER = logging.getLogger(__name__)

# IQ2 base64 photo payloads run a few hundred KB; cap well above that to reject junk.
_MAX_ENCODED_SIZE = 8_000_000


class PanelCommandStrings(StrEnum):
    AC_STATUS = "acStatus"
    CONNECT = "connect_v204"
    DATABASE = "database"
    DEALER_LOGO = "dealerLogo"
    DISARM_FROM_EMERGENCY = "disarm_from_emergency"
    DISARM_FROM_OPENLEARN_SENSOR = "disarm_from_openlearn_sensor"
    DISARM_FROM_ENTRY_DELAY = "disarm_the_panel_from_entry_delay"
    DISCONNECT = "disconnect"
    EXECUTE_SCENE = "execute_scene"
    GENERATE_EMERGENCY = "generate_emergency"
    PAIR_STATUS_REQUEST = "pair_status_request"
    PHOTO_FRAME_IMAGE_DOWNLOAD_REQUEST = "photoFrameImageDownloadRequest"
    PINGEVENT = "pingevent"
    QUICK_EXIT_STATE = "quick_exit_state"
    SPEAK = "speak_text"
    SYNC_DATABASE = "syncdatabase"
    TIMESYNC = "timeSync"
    UI_DELAY = "ui_delay"
    CHANGE_MASTER_VOLUME_LEVEL = "changeMasterVolumeLevel"
    CHANGE_DOORBELL_VOLUME_LEVEL = "changeDoorBellVolumeLevel"


class PanelCommands:
    def __init__(self, controller: QolsysController) -> None:
        self._controller = controller

    async def ac_status(self) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending ac_status command")
        command = MQTTCommand(self._controller, PanelCommandStrings.AC_STATUS)
        command.append("acStatus", "Connected")
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving ac_status command")
        return response

    async def arm(
        self,
        partition_id: str,
        arming_type: PartitionArmingType,
        user_code: str = "",
        exit_sounds: bool = False,
        instant_arm: bool = False,
        entry_delay: bool = True,
    ) -> dict[str, str]:
        LOGGER.debug(
            "MQTT Panel Client - Sending arm command: partition%s, arming_type:%s, exit_sounds:%s, instant_arm: %s, entry_delay:%s",
            partition_id,
            arming_type,
            exit_sounds,
            instant_arm,
            entry_delay,
        )

        user_id = 0

        partition = self._controller.state.partition(partition_id)
        if not partition:
            LOGGER.debug("MQTT Panel Client - arm command error - Unknown Partition")
            raise QolsysInvalidPartitionIdError(partition_id)

        if self._controller.settings.check_user_code_on_arm:
            # Do local user code verification to arm
            # Audit H3: check_user derives a PBKDF2 hash, so keep it off the loop.
            user_id = await asyncio.to_thread(self._controller.panel.check_user, user_code)
            if user_id == -1:
                LOGGER.debug("MQTT Panel Client - arm command error - user_code error")
                raise QolsysUserCodeError()

        exitSoundValue = "ON"
        if not exit_sounds:
            exitSoundValue = "OFF"

        entryDelay = "ON"
        if not entry_delay:
            entryDelay = "OFF"

        open_zone_list: list[str] = []
        bypass_open_zone_list: list[str] = []
        open_safety_zones: list[str] = []

        for zone in self._controller.state.zones:
            if zone.partition_id != partition_id or zone.sensorstatus not in TroubleZoneStatus:
                continue

            if zone.is_bypassable():
                bypass_open_zone_list.append(zone.zone_id)
            elif zone.is_safety():
                open_safety_zones.append(zone.zone_id)
            else:
                open_zone_list.append(zone.zone_id)

        # Audit L1: a safety zone (smoke, CO, water) cannot be bypassed, so arming
        # with one open used to go ahead silently. Restored as a hard error; the
        # integration surfaces it as "Zone bypass required".
        if open_safety_zones:
            LOGGER.warning("MQTT Panel Client - Cannot arm: open safety zones: %s", open_safety_zones)
            raise QolsysZoneBypassError(open_safety_zones)

        # Cannot bypass open zones if auto_bypass is disabled - return error
        if bypass_open_zone_list and self._controller.panel.AUTO_BYPASS == "false":
            LOGGER.debug(
                "MQTT Panel Client - Cannot arm: Open Zones that can be bypassed but AUTO_BYPASS is disabled: %s",
                bypass_open_zone_list,
            )
            raise QolsysZoneBypassError(bypass_open_zone_list)

        bypass_zone_str = "[" + ",".join(map(str, bypass_open_zone_list)) + "]"

        arming_command = {
            "operation_name": arming_type.value,
            "bypass_zoneid_set": bypass_zone_str,
            "userID": user_id,
            "partitionID": int(partition_id),  # Expect Int
            "exitSoundValue": exitSoundValue,
            "entryDelayValue": entryDelay,
            "multiplePartitionsSelected": False,
            "instant_arming": instant_arm,
            "final_exit_arming_selected": False,
            "manually_selected_zones": "[]",
            "operation_source": 1,
            "macAddress": self._controller.settings.random_mac,
        }

        ipc_request = [
            {
                "dataType": "string",
                "dataValue": json.dumps(arming_command),
            }
        ]

        command = MQTTCommand_Panel(self._controller)
        command.append_ipc_request(ipc_request)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving arm command: partition%s", partition_id)
        return response

    async def change_master_volume_level(self, volume_level: int) -> dict[str, Any] | None:
        LOGGER.debug("MQTT Panel Client - Sending change_master_volume_level command: volume_level:%s", volume_level)

        if not isinstance(volume_level, int) or not 0 <= volume_level <= 15:
            raise QolsysOperationError(f"Invalid master volume level: {volume_level} (must be an int in range 0-15)")

        volume_command = {
            "operation_name": PanelCommandStrings.CHANGE_MASTER_VOLUME_LEVEL,
            "volume_level": volume_level,
        }

        ipc_request = [
            {
                "dataType": "string",
                "dataValue": json.dumps(volume_command),
            }
        ]

        command = MQTTCommand_Panel(self._controller)
        command.append_ipc_request(ipc_request)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving change_master_volume_level command")
        return response

    async def change_doorbell_volume_level(self, volume_level: int) -> dict[str, Any] | None:
        LOGGER.debug(
            "MQTT Panel Client - Sending change_doorbell_volume_level command: volume_level:%s",
            volume_level,
        )

        if not isinstance(volume_level, int) or not 0 <= volume_level <= 7:
            raise QolsysOperationError(f"Invalid doorbell volume level: {volume_level} (must be an int in range 0-7)")

        volume_command = {
            "operation_name": PanelCommandStrings.CHANGE_DOORBELL_VOLUME_LEVEL,
            "stream_type": 0,
            "volume_level": volume_level,
            "request_id": "",
        }

        ipc_request = [
            {
                "dataType": "string",
                "dataValue": json.dumps(volume_command),
            }
        ]

        command = MQTTCommand_Panel(self._controller)
        command.append_ipc_request(ipc_request)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving change_doorbell_volume_level command")
        return response

    async def capture_photo(self, request_id: str, directory: str) -> dict[str, Any]:
        LOGGER.debug(
            "MQTT Panel Client - Sending capture_photo command: request_id:%s, directory:%s",
            request_id,
            directory,
        )

        if not request_id:
            raise ValueError("A non-empty request_id is required")

        ipc_request = [
            {
                "dataType": "string",
                "dataValue": request_id,
            },
            {
                "dataType": "string",
                "dataValue": directory,
            },
        ]

        command = MQTTCommand_CameraService(self._controller, CameraServiceTransactionType.CAPTURE_PIC)
        command.append_ipc_request(ipc_request)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving capture_photo command")
        return response

    async def delete_photo(self, filename: str) -> dict[str, Any]:
        LOGGER.debug(
            "MQTT Panel Client - Sending delete_photo command: filename:%s",
            filename,
        )

        if (
            not filename
            or PurePosixPath(filename).name != filename
            or "\\" in filename
            or not filename.lower().endswith(".jpg")
        ):
            raise ValueError("A single existing JPEG filename is required")

        ipc_request: list[dict[str, Any]] = [
            {
                "dataType": "int",
                "dataValue": 1,
            },
            {
                "dataType": "string",
                "dataValue": "../PeekInPhotos/" + filename,
            },
        ]

        command = MQTTCommand_CameraService(self._controller, CameraServiceTransactionType.DELETE_PIC)
        command.append_ipc_request(ipc_request)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving delete_photo command")
        return response

    async def photo_exists(self, directory: str, filename: str) -> bool:
        """Report photo presence from the raw panel response.

        Unlike download_photo, a present-but-unreadable file is reported as present
        (never mistaken for a deleted one), so snapshot cleanup won't drop a record's
        metadata while its image still lingers on the panel.
        """
        LOGGER.debug("MQTT Panel Client - Sending photo_exists check: directory:%s, filename:%s", directory, filename)

        resolved = PhotoDirectory(directory)
        if (
            not filename
            or PurePosixPath(filename).name != filename
            or "\\" in filename
            or not filename.lower().endswith(".jpg")
        ):
            raise ValueError("A single existing JPEG filename is required")

        command = MQTTCommand(self._controller, PanelCommandStrings.PHOTO_FRAME_IMAGE_DOWNLOAD_REQUEST)
        command.append("directory", resolved.value)
        command.append("photoFrameImageName", filename)
        response = await command.send_command()
        return bool(response.get("photoFrameImageString"))

    async def download_photo(self, directory: str, filename: str) -> bytes | None:
        LOGGER.debug(
            "MQTT Panel Client - Sending photo_frame_image_download_request command: directory:%s, filename:%s",
            directory,
            filename,
        )

        resolved = PhotoDirectory(directory)
        if (
            not filename
            or PurePosixPath(filename).name != filename
            or "\\" in filename
            or not filename.lower().endswith(".jpg")
        ):
            raise ValueError("A single existing JPEG filename is required")

        command = MQTTCommand(self._controller, PanelCommandStrings.PHOTO_FRAME_IMAGE_DOWNLOAD_REQUEST)
        command.append("directory", resolved.value)
        command.append("photoFrameImageName", filename)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving photo_frame_image_download_request command")

        encoded = response.get("photoFrameImageString")

        if not isinstance(encoded, str) or not encoded or len(encoded) > _MAX_ENCODED_SIZE:
            return None
        try:
            jpeg = base64.b64decode("".join(encoded.split()), validate=True)
        except (ValueError, binascii.Error) as error:
            raise QolsysOperationError("Panel returned invalid photo encoding") from error

        # IQ2 downloads include the camera buffer's zero padding after JPEG EOI.
        jpeg = jpeg.rstrip(b"\x00")
        if not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9"):
            return None

        return jpeg

    async def quick_exit(self, partition_id: str, delay_page_time: int = 120) -> dict[str, Any] | None:
        LOGGER.debug(
            "MQTT Panel Client - Sending quick_exit command: partition%s, delay_page_time:%s",
            partition_id,
            delay_page_time,
        )

        partition = self._controller.state.partition(partition_id)
        if not partition:
            LOGGER.debug("MQTT Panel Client - quick_exit command error - Unknown Partition: %s", partition_id)
            raise QolsysInvalidPartitionIdError(partition_id)

        if partition.system_status not in {PartitionSystemStatus.ARM_STAY, PartitionSystemStatus.ARM_NIGHT}:
            LOGGER.debug(
                "MQTT Panel Client - quick_exit command error - Partition %s is not in ARM_STAY or ARM_NIGHT state: %s",
                partition_id,
                partition.system_status,
            )
            raise CommandExecutionError(
                f"Partition {partition_id} is not in ARM_STAY or ARM_NIGHT state: {partition.system_status}"
            )

        # Panel honors quick_exit only while ARM-STAY and not in Alarm, with no
        # user-code or operation_source gating. operation_source/macAddress mirror arm() for parity.
        quick_exit_command = {
            "operation_name": PanelCommandStrings.QUICK_EXIT_STATE,
            "quick_exit_state": "Started",
            "delayPageTime": delay_page_time,
            "stateChangeTime": int(time.time() * 1000),
            "partitionID": int(partition_id),  # Expect Int
            "operation_source": 1,
            "macAddress": self._controller.settings.random_mac,
        }

        ipc_request = [
            {
                "dataType": "string",
                "dataValue": json.dumps(quick_exit_command),
            }
        ]

        command = MQTTCommand_Panel(self._controller)
        command.append_ipc_request(ipc_request)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving quick_exit command: partition%s", partition_id)
        return response

    async def connect(self) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending connect command")

        dhcpInfo = {
            "ipaddress": "",
            "gateway": "",
            "netmask": "",
            "dns1": "",
            "dns2": "",
            "dhcpServer": "",
            "leaseDuration": "",
        }

        command = MQTTCommand(self._controller, PanelCommandStrings.CONNECT)
        command.append("ipAddress", self._controller.settings.plugin_ip)
        command.append("pairing_request", True)
        command.append("macAddress", self._controller.settings.random_mac)
        command.append("remoteClientID", self._controller.settings.mqtt_remote_client_id)
        command.append("softwareVersion", "4.4.1")
        command.append("productType", "tab07_rk68")
        command.append("bssid", "")
        command.append("lastUpdateChecksum", "2132501716")
        command.append("dealerIconsCheckSum", "")
        command.append("remote_feature_support_version", "1")
        command.append("current_battery_status", "Normal")
        command.append("remote_panel_battery_percentage", 100)
        command.append("remote_panel_battery_temperature", 430)
        command.append("remote_panel_battery_status", 3)
        command.append("remote_panel_battery_scale", 100)
        command.append("remote_panel_battery_voltage", 4102)
        command.append("remote_panel_battery_present", True)
        command.append("remote_panel_battery_technology", "")
        command.append("remote_panel_battery_level", 100)
        command.append("remote_panel_battery_health", 2)
        command.append("remote_panel_plugged", 1)
        command.append("dhcpInfo", json.dumps(dhcpInfo))

        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving connect command")
        return response

    # The three database_remote_* commands below are a generic read/insert/delete
    # against any content-provider URI on the panel. Only the camera snapshot
    # (commands/camera.py) uses them, against one fixed URI with selections built
    # from a UUID it generated itself; nothing in the integration exposes them.

    async def database_remote_insert(self, uri: str, content_values: dict[str, Any]) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending database_insert command")
        command = MQTTCommand(self._controller, PanelCommandStrings.DATABASE)
        command.append("dbOperation", "insert")
        command.append("uri", uri)
        command.append("contentValues", content_values)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving database_insert command")
        return response

    async def database_remote_delete(
        self, uri: str, selection: str | None = None, selection_arguments: str | None = None
    ) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending database_delete command")
        command = MQTTCommand(self._controller, PanelCommandStrings.DATABASE)
        command.append("dbOperation", "delete")
        command.append("uri", uri)
        if selection is not None:
            command.append("selection", selection)
        if selection_arguments is not None:
            command.append("selectionArgs", selection_arguments)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving database_delete command")
        return response

    async def database_remote_read(
        self,
        uri: str,
        projection: str | None = None,
        selection: str | None = None,
        selection_arguments: str | None = None,
        sort_order: str | None = None,
    ) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending database_read command")
        command = MQTTCommand(self._controller, PanelCommandStrings.DATABASE)
        command.append("dbOperation", "read")
        command.append("uri", uri)
        if projection is not None:
            command.append("projection", projection)
        if selection is not None:
            command.append("selection", selection)
        if selection_arguments is not None:
            command.append("selectionArgs", selection_arguments)
        if sort_order is not None:
            command.append("sortOrder", sort_order)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving database_read command")
        return response

    async def dealer_logo(self) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending dealerLogo command")
        command = MQTTCommand(self._controller, PanelCommandStrings.DEALER_LOGO)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving dealerLogo command")
        return response

    async def disarm(self, partition_id: str, user_code: str = "", silent_disarming: bool = False) -> dict[str, Any]:
        partition = self._controller.state.partition(partition_id)
        if not partition:
            LOGGER.error("MQTT Panel Client - disarm command error - Unknow Partition")
            raise QolsysInvalidPartitionIdError(partition_id)

        # Do local user code verification
        user_id = 1
        if self._controller.settings.check_user_code_on_disarm:
            # Audit H3: check_user derives a PBKDF2 hash, so keep it off the loop.
            user_id = await asyncio.to_thread(self._controller.panel.check_user, user_code)
            if user_id == -1:
                LOGGER.debug("MQTT Panel Client - disarm command error - user_code error")
                raise QolsysUserCodeError()

        async def get_mqtt_disarm_command(silent_disarming: bool) -> str:
            if partition.alarm_state == PartitionAlarmState.ALARM:
                return PanelCommandStrings.DISARM_FROM_EMERGENCY
            if partition.system_status in {
                PartitionSystemStatus.ARM_AWAY_EXIT_DELAY,
                PartitionSystemStatus.ARM_STAY_EXIT_DELAY,
                PartitionSystemStatus.ARM_NIGHT_EXIT_DELAY,
            }:
                return PanelCommandStrings.DISARM_FROM_OPENLEARN_SENSOR
            if partition.system_status in {
                PartitionSystemStatus.ARM_AWAY,
                PartitionSystemStatus.ARM_STAY,
                PartitionSystemStatus.ARM_NIGHT,
            }:
                await self.ui_delay(partition_id, silent_disarming)
                return PanelCommandStrings.DISARM_FROM_ENTRY_DELAY

            return PanelCommandStrings.DISARM_FROM_OPENLEARN_SENSOR

        mqtt_disarm_command = await get_mqtt_disarm_command(silent_disarming)
        LOGGER.debug(
            "MQTT Panel Client - Sending disarm command - check_user_code:%s",
            self._controller.settings.check_user_code_on_disarm,
        )

        disarm_command = {
            "operation_name": mqtt_disarm_command,
            "userID": user_id,
            "partitionID": int(partition_id),  # INT EXPECTED
            "operation_source": 1,
            "macAddress": self._controller.settings.random_mac,
        }

        ipc_request = [
            {
                "dataType": "string",
                "dataValue": json.dumps(disarm_command),
            }
        ]

        command = MQTTCommand_Panel(self._controller)
        command.append_ipc_request(ipc_request)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving disarm command")
        return response

    async def disconnect(self) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending disconnect command")
        command = MQTTCommand(self._controller, PanelCommandStrings.DISCONNECT)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving disconnect command")
        return response

    async def pair_status_request(self) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending pair_status_request command")
        command = MQTTCommand(self._controller, PanelCommandStrings.PAIR_STATUS_REQUEST)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving pair_status_request command")
        return response

    async def execute_scene(self, scene_id: str) -> dict[str, Any] | None:
        LOGGER.debug("MQTT Panel Client - Sending execute_scene command")
        scene = self._controller.state.scene(scene_id)
        if not scene:
            LOGGER.debug("MQTT Panel Client - command_execute_scene Erro - Unknown Scene: %s", scene_id)
            return None

        scene_command = {
            "operation_name": PanelCommandStrings.EXECUTE_SCENE,
            "scene_id": int(scene.scene_id),
            "operation_source": 1,
            "macAddress": self._controller.settings.random_mac,
        }

        ipc_request = [
            {
                "dataType": "string",
                "dataValue": json.dumps(scene_command),
            }
        ]

        command = MQTTCommand_Panel(self._controller)
        command.append_ipc_request(ipc_request)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving execute_scene command")
        return response

    async def pingevent(self) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending pingevent command")
        command = MQTTCommand(self._controller, "pingevent")
        command.append("remote_panel_status", "Active")
        command.append("macAddress", self._controller.settings.random_mac)
        command.append("ipAddress", self._controller.settings.plugin_ip)
        command.append("current_battery_status", "Normal")
        command.append("remote_panel_battery_percentage", 100)
        command.append("remote_panel_battery_temperature", 430)
        command.append("remote_panel_battery_status", 3)
        command.append("remote_panel_battery_scale", 100)
        command.append("remote_panel_battery_voltage", 4102)
        command.append("remote_panel_battery_present", True)
        command.append("remote_panel_battery_technology", "")
        command.append("remote_panel_battery_level", 100)
        command.append("remote_panel_battery_health", 2)
        command.append("remote_panel_plugged", 1)

        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving pingevent command")
        return response

    async def speak(self, text: str) -> dict[str, Any] | None:
        LOGGER.debug("MQTT Panel Client - Sending panel_speak command")

        speak_command = {
            "operation_name": PanelCommandStrings.SPEAK,
            "tts_text": text,
            "operation_source": 1,
            "macAddress": self._controller.settings.random_mac,
        }

        ipc_request = [
            {
                "dataType": "string",
                "dataValue": json.dumps(speak_command),
            }
        ]

        command = MQTTCommand_Panel(self._controller)
        command.append_ipc_request(ipc_request)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving panel_speak command")
        return response

    async def sync_database(self) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending syncdatabase command")
        command = MQTTCommand(self._controller, PanelCommandStrings.SYNC_DATABASE)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving syncdatabase command")
        return response

    async def timesync(self) -> dict[str, Any]:
        LOGGER.debug("MQTT Panel Client - Sending timeSync command")
        command = MQTTCommand(self._controller, PanelCommandStrings.TIMESYNC)
        command.append("startTimestamp", int(time.time()))
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving timeSync command")
        return response

    async def trigger_auxilliary(self, partition_id: str, silent: bool) -> dict[str, Any] | None:
        LOGGER.debug("MQTT Panel Client - Sending panel_trigger_auxilliary command")

        partition = self._controller.state.partition(partition_id)
        if not partition:
            LOGGER.debug("MQTT Panel Client - command_panel_trigger_auxilliary Error - Unknow Partition: %s", partition_id)
            return None

        trigger_command = {
            "operation_name": PanelCommandStrings.GENERATE_EMERGENCY,
            "partitionID": int(partition_id),
            "zoneID": int(self._controller._zone_id),
            "emergencyType": "Silent Auxiliary Emergency" if silent else "Auxiliary Emergency",
            "operation_source": 1,
            "macAddress": self._controller.settings.random_mac,
        }

        ipc_request = [
            {
                "dataType": "string",
                "dataValue": json.dumps(trigger_command),
            }
        ]

        command = MQTTCommand_Panel(self._controller)
        command.append_ipc_request(ipc_request)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving panel_trigger_auxilliary command")
        return response

    async def trigger_police(self, partition_id: str, silent: bool) -> dict[str, Any] | None:
        LOGGER.debug("MQTT Panel Client - Sending panel_trigger_police command")

        partition = self._controller.state.partition(partition_id)
        if not partition:
            LOGGER.debug("MQTT Panel Client - command_panel_trigger_police Error - Unknow Partition: %s", partition_id)
            return None

        trigger_command = {
            "operation_name": PanelCommandStrings.GENERATE_EMERGENCY,
            "partitionID": int(partition_id),
            "zoneID": int(self._controller._zone_id),
            "emergencyType": "Silent Police Emergency" if silent else "Police Emergency",
            "operation_source": 1,
            "macAddress": self._controller.settings.random_mac,
        }

        ipc_request = [
            {
                "dataType": "string",
                "dataValue": json.dumps(trigger_command),
            }
        ]

        command = MQTTCommand_Panel(self._controller)
        command.append_ipc_request(ipc_request)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving panel_trigger_police command")
        return response

    async def trigger_fire(self, partition_id: str) -> dict[str, Any] | None:
        LOGGER.debug("MQTT Panel Client - Sending panel_trigger_fire command")

        partition = self._controller.state.partition(partition_id)
        if not partition:
            LOGGER.debug("MQTT Panel Client - command_panel_trigger_fire Error - Unknow Partition: %s", partition_id)
            return None

        trigger_command = {
            "operation_name": PanelCommandStrings.GENERATE_EMERGENCY,
            "partitionID": int(partition_id),
            "zoneID": int(self._controller._zone_id),
            "emergencyType": "Fire Emergency",
            "operation_source": 1,
            "macAddress": self._controller.settings.random_mac,
        }

        ipc_request = [
            {
                "dataType": "string",
                "dataValue": json.dumps(trigger_command),
            }
        ]

        command = MQTTCommand_Panel(self._controller)
        command.append_ipc_request(ipc_request)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving panel_trigger_fire command")
        return response

    async def ui_delay(self, partition_id: str, silent_disarming: bool = False) -> dict[str, Any] | None:
        LOGGER.debug("MQTT Panel Client - Sending ui_delay command")
        command = MQTTCommand_Panel(self._controller)

        # partition state needs to be sent for ui_delay to work
        partition = self._controller.state.partition(partition_id)
        if not partition:
            LOGGER.error("ui_delay error: invalid partition %s", partition_id)
            return None

        arming_command = {
            "operation_name": PanelCommandStrings.UI_DELAY,
            "panel_status": partition.system_status,
            "userID": 0,
            "partitionID": partition_id,  # STR EXPECTED
            "silentDisarming": silent_disarming,
            "operation_source": 1,
            "macAddress": self._controller.settings.random_mac,
        }

        ipcRequest = [
            {
                "dataType": "string",
                "dataValue": json.dumps(arming_command),
            }
        ]

        command.append("ipcRequest", ipcRequest)
        response = await command.send_command()
        LOGGER.debug("MQTT Panel Client - Receiving ui_delay command")
        return response
