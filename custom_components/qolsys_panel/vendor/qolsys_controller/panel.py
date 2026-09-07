from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from .automation.device import QolsysAutomationDevice
from .automation_adc.device import QolsysAutomationDeviceADC
from .automation_powerg.device import QolsysAutomationDevicePowerG
from .automation_zigbee.device import QolsysAutomationDeviceZigbee
from .automation_zwave.device import QolsysAutomationDeviceZwave
from .errors import QolsysConfigError
from .observable import Event

from .database.db import QolsysDB
from .enum_qolsys import (
    AutomationDeviceProtocol,
    PartitionAlarmState,
    PartitionAlarmType,
    PartitionQuickExitState,
    PartitionSystemStatus,
    QolsysNotification,
    QolsysPanelType,
)
from .partition import QolsysPartition
from .scene import QolsysScene
from .users import QolsysUser
from .weather import QolsysForecast, QolsysWeather
from .zone import QolsysZone

LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .controller import QolsysController


class QolsysPanel:
    def __init__(self, controller: QolsysController) -> None:
        self._controller = controller
        self._db = QolsysDB()

        # Partition settings
        self.settings_partition = ["SYSTEM_STATUS", "EXIT_SOUNDS", "ENTRY_DELAYS", "SYSTEM_STATUS_CHANGED_TIME"]
        self.state_partition = ["ALARM_STATE", "QUICK_EXIT_STATE"]

        # Panel settings
        self.settings_panel = [
            "PANEL_TAMPER_STATE",
            "AC_STATUS",
            "BATTERY_STATUS",
            "FAIL_TO_COMMUNICATE",
            "SECURE_ARMING",
            "AUTO_BYPASS",
            "AUTO_STAY",
            "AUTO_ARM_STAY",
            "AUTO_EXIT_EXTENSION",
            "FINAL_EXIT_DOOR_ARMING",
            "NO_ARM_LOW_BATTERY",
            "TEMPFORMAT",
            "LANGUAGE",
            "COUNTRY",
            "SYSTEM_TIME",
            "HARDWARE_VERSION",
            "TIMER_NORMAL_ENTRY_DELAY",
            "TIMER_NORMAL_EXIT_DELAY",
            "TIMER_LONG_ENTRY_DELAY",
            "TIMER_LONG_EXIT_DELAY",
            "ZWAVE_CONTROLLER",
            "ZWAVE_CARD",
            "POLICE_PANIC_ENABLED",
            "FIRE_PANIC_ENABLED",
            "AUXILIARY_PANIC_ENABLED",
            "NIGHTMODE_SETTINGS",
            "NIGHT_SETTINGS_STATE",
            "SAFETY_SENSOR_QUICK_EXIT",
            "PARTITIONS",
            "SIX_DIGIT_USER_CODE",
            "SHOW_SECURITY_SENSORS",
            "SYSTEM_LOGGED_IN_USER",
            "PANEL_SCENES_SETTING",
            "CONTROL_4",
            "ZWAVE_FIRM_WARE_VERSION",
            "FINAL_EXIT_DOOR_ARMING",
            "NO_ARM_LOW_BATTERY",
            "MAC_ADDRESS",
            "LAST_UPDATE_IQ_REMOTE_PATCH_CKECKSUM_N",
        ]

        self._users: list[QolsysUser] = []
        self._unique_id: str = ""

        self._imei: str = ""
        self._product_type: QolsysPanelType = QolsysPanelType.UNKNOWN

    def read_users_file(self) -> None:
        # Clear existing users list
        self._users.clear()

        # Loading user_code data from users.conf file if exists
        if self._controller.settings.users_file_path.is_file():
            try:
                path = self._controller.settings.users_file_path
                with path.open("r", encoding="utf-8") as file:
                    try:
                        users = json.load(file)
                        for user in users:
                            qolsys_user = QolsysUser()
                            qolsys_user.id = user.get("id")
                            qolsys_user.user_code = user.get("user_code")
                            self._users.append(qolsys_user)

                    except json.JSONDecodeError:
                        raise QolsysConfigError("users.conf file json error")

            except FileNotFoundError:
                raise QolsysConfigError("users.conf file not found")

        return

    @property
    def db(self) -> QolsysDB:
        return self._db

    @property
    def PANEL_TAMPER_STATE(self) -> str:
        self._PANEL_TAMPER_STATE = self.db.get_setting_panel("PANEL_TAMPER_STATE")
        return self._PANEL_TAMPER_STATE

    @property
    def AC_STATUS(self) -> str:
        self._AC_STATUS = self.db.get_setting_panel("AC_STATUS")
        return self._AC_STATUS

    @property
    def BATTERY_STATUS(self) -> str:
        self._BATTERY_STATUS = self.db.get_setting_panel("BATTERY_STATUS")
        return self._BATTERY_STATUS

    @property
    def FAIL_TO_COMMUNICATE(self) -> str:
        self._FAIL_TO_COMMUNICATE = self.db.get_setting_panel("FAIL_TO_COMMUNICATE")
        return self._FAIL_TO_COMMUNICATE

    @property
    def SECURE_ARMING(self) -> str:
        self._SECURE_ARMING = self.db.get_setting_panel("SECURE_ARMING")
        return self._SECURE_ARMING

    @property
    def AUTO_BYPASS(self) -> str:
        self._AUTO_BYPASS = self.db.get_setting_panel("AUTO_BYPASS")
        return self._AUTO_BYPASS

    @property
    def AUTO_STAY(self) -> str:
        self._AUTO_STAY = self.db.get_setting_panel("AUTO_STAY")
        return self._AUTO_STAY

    @property
    def AUTO_ARM_STAY(self) -> str:
        self._AUTO_ARM_STAY = self.db.get_setting_panel("AUTO_ARM_STAY")
        return self._AUTO_ARM_STAY

    @property
    def AUTO_EXIT_EXTENSION(self) -> str:
        self._AUTO_EXIT_EXTENSION = self.db.get_setting_panel("AUTO_EXIT_EXTENSION")
        return self._AUTO_EXIT_EXTENSION

    @property
    def FINAL_EXIT_DOOR_ARMING(self) -> str:
        self._FINAL_EXIT_DOOR_ARMING = self.db.get_setting_panel("FINAL_EXIT_DOOR_ARMING")
        return self._FINAL_EXIT_DOOR_ARMING

    @property
    def NO_ARM_LOW_BATTERY(self) -> str:
        self._NO_ARM_LOW_BATTERY = self.db.get_setting_panel("NO_ARM_LOW_BATTERY")
        return self._NO_ARM_LOW_BATTERY

    @property
    def TEMPFORMAT(self) -> str:
        self._TEMPFORMAT = self.db.get_setting_panel("TEMPFORMAT")
        return self._TEMPFORMAT

    @property
    def LANGUAGE(self) -> str:
        self._LANGUAGE = self.db.get_setting_panel("LANGUAGE")
        return self._LANGUAGE

    @property
    def COUNTRY(self) -> str:
        self._COUNTRY = self.db.get_setting_panel("COUNTRY")
        return self._COUNTRY

    @property
    def SYSTEM_TIME(self) -> str:
        self._SYSTEM_TIME = self.db.get_setting_panel("SYSTEM_TIME")
        return self._SYSTEM_TIME

    @property
    def HARDWARE_VERSION(self) -> str:
        self._HARDWARE_VERSION = self.db.get_setting_panel("HARDWARE_VERSION")
        return self._HARDWARE_VERSION

    @property
    def ZWAVE_FIRM_WARE_VERSION(self) -> str:
        self._ZWAVE_FIRM_WARE_VERSION = self.db.get_setting_panel("ZWAVE_FIRM_WARE_VERSION")
        return self._ZWAVE_FIRM_WARE_VERSION

    @property
    def ZWAVE_CONTROLLER(self) -> str:
        self._ZWAVE_CONTROLLER = self.db.get_setting_panel("ZWAVE_CONTROLLER")
        return self._ZWAVE_CONTROLLER

    @property
    def ZWAVE_CARD(self) -> str:
        self._ZWAVE_CARD = self.db.get_setting_panel("ZWAVE_CARD")
        return self._ZWAVE_CARD

    @property
    def POLICE_PANIC_ENABLED(self) -> str:
        self._POLICE_PANIC_ENABLED = self.db.get_setting_panel("POLICE_PANIC_ENABLED")
        return self._POLICE_PANIC_ENABLED

    @property
    def FIRE_PANIC_ENABLED(self) -> str:
        self._FIRE_PANIC_ENABLED = self.db.get_setting_panel("FIRE_PANIC_ENABLED")
        return self._FIRE_PANIC_ENABLED

    @property
    def AUXILIARY_PANIC_ENABLED(self) -> str:
        self._AUXILIARY_PANIC_ENABLED = self.db.get_setting_panel("AUXILIARY_PANIC_ENABLED")
        return self._AUXILIARY_PANIC_ENABLED

    @property
    def PARTITIONS(self) -> str:
        self._PARTITIONS = self.db.get_setting_panel("PARTITIONS")
        return self._PARTITIONS

    @property
    def SIX_DIGIT_USER_CODE(self) -> str:
        self._SIX_DIGIT_USER_CODE = self.db.get_setting_panel("SIX_DIGIT_USER_CODE")
        return self._SIX_DIGIT_USER_CODE

    @property
    def CONTROL_4(self) -> str:
        self._CONTROL_4 = self.db.get_setting_panel("CONTROL_4")
        return self._CONTROL_4

    @property
    def NIGHTMODE_SETTINGS(self) -> str:
        self._NIGHTMODE_SETTINGS = self.db.get_setting_panel("NIGHTMODE_SETTINGS")
        return self._NIGHTMODE_SETTINGS

    @property
    def NIGHT_SETTINGS_STATE(self) -> str:
        self._NIGHT_SETTINGS_STATE = self.db.get_setting_panel("NIGHT_SETTINGS_STATE")
        return self._NIGHT_SETTINGS_STATE

    @property
    def SHOW_SECURITY_SENSORS(self) -> str:
        self._SHOW_SECURITY_SENSORS = self.db.get_setting_panel("SHOW_SECURITY_SENSORS")
        return self._SHOW_SECURITY_SENSORS

    @property
    def TIMER_NORMAL_ENTRY_DELAY(self) -> str:
        self._TIMER_NORMAL_ENTRY_DELAY = self.db.get_setting_panel("TIMER_NORMAL_ENTRY_DELAY")
        return self._TIMER_NORMAL_ENTRY_DELAY

    @property
    def TIMER_NORMAL_EXIT_DELAY(self) -> str:
        self._TIMER_NORMAL_EXIT_DELAY = self.db.get_setting_panel("TIMER_NORMAL_EXIT_DELAY")
        return self._TIMER_NORMAL_EXIT_DELAY

    @property
    def TIMER_LONG_ENTRY_DELAY(self) -> str:
        self._TIMER_LONG_ENTRY_DELAY = self.db.get_setting_panel("TIMER_LONG_ENTRY_DELAY")
        return self._TIMER_LONG_ENTRY_DELAY

    @property
    def MAC_ADDRESS(self) -> str:
        self._MAC_ADDRESS = self.db.get_setting_panel("MAC_ADDRESS")
        return self._MAC_ADDRESS

    @MAC_ADDRESS.setter
    def MAC_ADDRESS(self, value: str) -> None:
        self._MAC_ADDRESS = value

    @property
    def unique_id(self) -> str:
        mac_address = self.MAC_ADDRESS
        return mac_address.replace(":", "")

    @property
    def TIMER_LONG_EXIT_DELAY(self) -> str:
        self._TIMER_LONG_EXIT_DELAY = self.db.get_setting_panel("TIMER_LONG_ENTRY_DELAY")
        return self._TIMER_LONG_EXIT_DELAY

    @property
    def LAST_UPDATE_IQ_REMOTE_PATCH_CKECKSUM_N(self) -> str:
        self._LAST_UPDATE_IQ_REMOTE_PATCH_CKECKSUM_N = self.db.get_setting_panel("LAST_UPDATE_IQ_REMOTE_PATCH_CKECKSUM_N")
        return self._LAST_UPDATE_IQ_REMOTE_PATCH_CKECKSUM_N

    @property
    def SAFETY_SENSOR_QUICK_EXIT(self) -> str:
        self._SAFETY_SENSOR_QUICK_EXIT = self.db.get_setting_panel("SAFETY_SENSOR_QUICK_EXIT")
        return self._SAFETY_SENSOR_QUICK_EXIT

    @property
    def imei(self) -> str:
        return self._imei

    @imei.setter
    def imei(self, value: str) -> None:
        self._imei = value

    @property
    def product_type(self) -> QolsysPanelType:
        return self._product_type

    @product_type.setter
    def product_type(self, value: str) -> None:
        try:
            self._product_type = QolsysPanelType(value)
        except ValueError:
            LOGGER.error("Unknown panel product type: %s, please report", value)
            self._product_type = QolsysPanelType.UNKNOWN

    @property
    def SYSTEM_LOGGED_IN_USER(self) -> str:
        self._SYSTEM_LOGGED_IN_USER = self.db.get_setting_panel("SYSTEM_LOGGED_IN_USER")
        return self._SYSTEM_LOGGED_IN_USER

    @SYSTEM_LOGGED_IN_USER.setter
    def SYSTEM_LOGGED_IN_USER(self, value: str) -> None:
        self._SYSTEM_LOGGED_IN_USER = value

    @property
    def PANEL_SCENES_SETTING(self) -> str:
        self._PANEL_SCENES_SETTING = self.db.get_setting_panel("PANEL_SCENES_SETTING")
        return self.PANEL_SCENES_SETTING

    async def load_database(self, database: Any | None) -> None:
        self.db.load_db(database)
        self._controller.state.sync_partitions_data(self.get_partitions_from_db())
        self._controller.state.sync_zones_data(self.get_zones_from_db())
        self._controller.state.sync_automation_devices_data(self.get_automation_devices_from_db())
        self._controller.state.sync_scenes_data(self.get_scenes_from_db())
        self._controller.state.sync_weather_data(self.get_weather_from_db())

        LOGGER.debug("sync_data - update automation devices z-wave devices states")
        for autdev in self._controller.state.automation_devices:
            if isinstance(autdev, QolsysAutomationDeviceZwave):
                await autdev.zwave_report()

        # Validate all local user match a Qolsys Panel user
        qolsys_users = self.db.get_users()
        qolsys_user_list = []
        for qolsys_user in qolsys_users:
            try:
                userid = int(qolsys_user.get("userid", ""))
            except ValueError:
                LOGGER.error("Invalid userid in panel database: %s", qolsys_user.get("userid", ""))
                userid = -1

            qolsys_user_list.append(userid)

        for local_user in self._users:
            if local_user.id not in qolsys_user_list:
                LOGGER.error("ID %s from users.conf file not found in panel database", local_user.id)

        # Check associated zone_id in iqremotesettins table
        LOGGER.debug("Checking iqremotesettings table for zone_id matching panel MAC address")
        iqremote_settings_list = self.db.get_iqremote_settings()
        for iqremote in iqremote_settings_list:
            if (
                self._controller.settings.random_mac.replace(":", "").lower()
                == iqremote.get("mac_address", "").replace(":", "").lower()
            ):
                self._controller._zone_id = iqremote.get("zone_id", "")
                LOGGER.debug("Found matching zone_id: %s", self._controller._zone_id)
                break

    # Parse Z-Wave message
    def parse_zwave_message(self, data: dict[str, Any]) -> None:
        zwave = data.get("ZWAVE_RESPONSE", "")
        payload = base64.b64decode(zwave.get("ZWAVE_PAYLOAD", "")).hex()
        node_id: str = str(zwave.get("NODE_ID", 0))

        # Update Atomation Device Z-Wave Service with raw payload
        automation_device = self._controller.state.automation_device(node_id)
        if isinstance(automation_device, QolsysAutomationDeviceZwave):
            automation_device.update_raw(bytes.fromhex(payload))

    # Parse panel update to database
    def parse_iq2meid_message(self, data: dict[str, Any]) -> None:  # noqa: C901, PLR0912, PLR0915
        eventName = data.get("eventName")
        dbOperation = data.get("dbOperation", "")
        uri = data.get("uri")

        match eventName:
            case "stopScreenCapture":
                pass

            case "primaryDisconnect":
                LOGGER.info("Main Panel Disconnect")

            case "eventNameDoorBell":
                LOGGER.debug("Doorbell Event: %s", json.dumps(data))
                self._controller.state.notify(Event(QolsysNotification.PANEL_DOORBELL, self, data))

            case "chime":
                LOGGER.debug("Chime Event: %s", json.dumps(data))
                self._controller.state.notify(Event(QolsysNotification.PANEL_CHIME, self, data))

            case "dbChanged":
                match dbOperation:
                    case "update":
                        content_values = data.get("contentValues", "")
                        selection = data.get("selection")
                        selection_argument = data.get("selectionArgs")

                        match uri:
                            # Update Settings Content Provider
                            case self.db.table_qolsyssettings.uri:
                                name = content_values.get("name", "")
                                new_value = content_values.get("value", "")
                                old_value = self.db.get_setting_panel(name)
                                self.db.table_qolsyssettings.update(selection, selection_argument, content_values)

                                # Update Panel Settings - Send notification if settings ha changed
                                if name in self.settings_panel and old_value != new_value:
                                    LOGGER.debug("Panel Setting - %s: %s", name, new_value)
                                    self._controller.state.notify(
                                        Event(QolsysNotification.PANEL_SETTINGS_UPDATE, self, self.to_event_dict())
                                    )

                                # Update Partition setting - Send notification if setting has changed
                                if name in self.settings_partition:
                                    partition_id = content_values.get("partition_id", "")
                                    partition = self._controller.state.partition(partition_id)
                                    if partition is not None:
                                        match name:
                                            case "SYSTEM_STATUS":
                                                partition.system_status = PartitionSystemStatus(new_value)
                                            case "SYSTEM_STATUS_CHANGED_TIME":
                                                partition.system_status_changed_time = new_value
                                            case "EXIT_SOUNDS":
                                                partition.exit_sounds = new_value
                                            case "ENTRY_DELAYS":
                                                partition.entry_delays = new_value

                            # Update Sensor Content Provider
                            case self.db.table_sensor.uri:
                                self.db.table_sensor.update(selection, selection_argument, content_values)
                                zoneid = content_values.get("zoneid", "")
                                zone = self._controller.state.zone(zone_id=zoneid)
                                if zone is not None:
                                    zone.update(content_values)

                            # Update State
                            case self.db.table_state.uri:
                                name = content_values.get("name", "")
                                new_value = content_values.get("value", "")
                                partition_id = content_values.get("partition_id", "")
                                self.db.table_state.update(selection, selection_argument, content_values)

                                if name in self.state_partition:
                                    partition = self._controller.state.partition(partition_id)
                                    if partition is not None:
                                        match name:
                                            case "ALARM_STATE":
                                                partition.alarm_state = PartitionAlarmState(new_value)
                                            case "QUICK_EXIT_STATE":
                                                delay = 0
                                                start_time = 0
                                                extra = content_values.get("extraparams", "")
                                                if extra:
                                                    try:
                                                        extra_json = json.loads(extra)
                                                        delay = int(extra_json.get("delayPageTime", 0) or 0)
                                                        start_time = int(extra_json.get("stateChangeTime", 0) or 0)
                                                    except (ValueError, TypeError, json.JSONDecodeError):
                                                        pass
                                                try:
                                                    partition.quick_exit_state = PartitionQuickExitState(new_value)
                                                    partition.quick_exit_delay = delay
                                                    partition.quick_exit_start_time = start_time
                                                except ValueError:
                                                    LOGGER.error(
                                                        "Partition%s (%s) - Invalid quick_exit_state: %s",
                                                        partition._id,
                                                        partition._name,
                                                        new_value,
                                                    )

                            # Update heat_map
                            case self.db.table_heat_map.uri:
                                self.db.table_heat_map.update(selection, selection_argument, content_values)

                            # Update master_slave
                            case self.db.table_master_slave.uri:
                                self.db.table_master_slave.update(selection, selection_argument, content_values)

                            # Update dashboard_msgs
                            case self.db.table_dashboard_msgs.uri:
                                self.db.table_dashboard_msgs.update(selection, selection_argument, content_values)

                            # Update PartitionContentProvider
                            case self.db.table_partition.uri:
                                self.db.table_partition.update(selection, selection_argument, content_values)
                                partition_id = content_values.get("partition_id", "")
                                partition = self._controller.state.partition(partition_id)
                                if partition is not None:
                                    partition.update_partition(content_values)

                            # Update History Content Provider
                            case self.db.table_history.uri:
                                self.db.table_history.update(selection, selection_argument, content_values)

                            # Update DimmerLightsContentProvider
                            case self.db.table_dimmer.uri:
                                self.db.table_dimmer.update(selection, selection_argument, content_values)
                                node_id = content_values.get("node_id", "")

                            # Update Thermostat Content Provider
                            case self.db.table_thermostat.uri:
                                self.db.table_thermostat.update(selection, selection_argument, content_values)
                                node_id = content_values.get("node_id", "")

                            # Update DoorLockContentProvider
                            case self.db.table_doorlock.uri:
                                self.db.table_doorlock.update(selection, selection_argument, content_values)
                                node_id = content_values.get("node_id", "")

                            # Update ZwaveContentProvider
                            case self.db.table_zwave_node.uri:
                                self.db.table_zwave_node.update(selection, selection_argument, content_values)
                                node_id = content_values.get("node_id", "")

                                # Update Automation Device if exist
                                automation_device = self._controller.state.automation_device(node_id)
                                if isinstance(automation_device, QolsysAutomationDeviceZwave):
                                    automation_device.update_zwave_device(content_values)

                            # Update Z-Wave History Content Provier
                            case self.db.table_zwave_history.uri:
                                self.db.table_zwave_history.update(selection, selection_argument, content_values)

                            # Update AutomationDeviceContentProvider
                            case self.db.table_automation.uri:
                                self.db.table_automation.update(selection, selection_argument, content_values)
                                virtual_node_id = content_values.get("virtual_node_id", "")
                                automation_device = self._controller.state.automation_device(virtual_node_id)
                                if automation_device is not None:
                                    automation_device.update_automation_device(content_values)

                            # Update Alarmed Sensor Content Provider
                            case self.db.table_alarmedsensor.uri:
                                self.db.table_alarmedsensor.update(selection, selection_argument, content_values)

                            # Update IQ Remote Settings Content Provider
                            case self.db.table_iqremotesettings.uri:
                                self.db.table_iqremotesettings.update(selection, selection_argument, content_values)

                            # Update Scene Content Provider
                            case self.db.table_scene.uri:
                                self.db.table_scene.update(selection, selection_argument, content_values)
                                scene_id = content_values.get("scene_id", "")
                                scene = self._controller.state.scene(scene_id)
                                if scene is not None and isinstance(scene, QolsysScene):
                                    scene.update(content_values)

                            # Update Trouble Conditions
                            case self.db.table_trouble_conditions.uri:
                                self.db.table_trouble_conditions.update(selection, selection_argument, content_values)

                            # Update EU_EVENT:
                            case self.db.table_eu_event.uri:
                                self.db.table_eu_event.update(selection, selection_argument, content_values)

                            # Update PowerG Device
                            case self.db.table_powerg_device.uri:
                                self.db.table_powerg_device.update(selection, selection_argument, content_values)
                                short_id = content_values.get("shortID", "")
                                zone = self._controller.state.zone_from_short_id(short_id)
                                if zone is not None:
                                    zone.update_powerg(content_values)

                            # Update Weather
                            case self.db.table_weather.uri:
                                self.db.table_weather.update(selection, selection_argument, content_values)
                                self._controller.state.sync_weather_data(self.get_weather_from_db())

                            # Update Zwave Association Group
                            case self.db.table_zwave_association_goup.uri:
                                self.db.table_zwave_association_goup.update(selection, selection_argument, content_values)

                            # Update Zwave Other
                            case self.db.table_zwave_other.uri:
                                self.db.table_zwave_other.update(selection, selection_argument, content_values)

                            # Country Locale
                            case self.db.table_country_locale.uri:
                                self.db.table_country_locale.update(selection, selection_argument, content_values)

                            # Virtual device
                            case self.db.table_virtual_device.uri:
                                self.db.table_virtual_device.update(selection, selection_argument, content_values)

                                # Update ADC devices in automation devices list
                                virtual_node_id = content_values.get("device_id", "")
                                automation_device = self._controller.state.automation_device(virtual_node_id)
                                if isinstance(automation_device, QolsysAutomationDeviceADC):
                                    automation_device.update_adc_device(content_values)

                            # Output Rules
                            case self.db.table_output_rules.uri:
                                self.db.table_output_rules.update(selection, selection_argument, content_values)

                            case _:
                                LOGGER.debug("iq2meid updating unknow uri:%s", uri)
                                LOGGER.debug(data)

                    case "delete":
                        selection = data.get("selection")
                        selection_argument = data.get("selectionArgs")

                        match uri:
                            case self.db.table_sensor.uri:
                                self.db.table_sensor.delete(selection, selection_argument)
                                self._controller.state.sync_zones_data(self.get_zones_from_db())

                            case self.db.table_iqremotesettings.uri:
                                self.db.table_iqremotesettings.delete(selection, selection_argument)

                            case self.db.table_state.uri:
                                self.db.table_state.delete(selection, selection_argument)

                            case self.db.table_master_slave.uri:
                                self.db.table_master_slave.delete(selection, selection_argument)

                            case self.db.table_qolsyssettings.uri:
                                self.db.table_qolsyssettings.delete(selection, selection_argument)

                            case self.db.table_alarmedsensor.uri:
                                self.db.table_alarmedsensor.delete(selection, selection_argument)
                                self._controller.state.sync_partitions_data(self.get_partitions_from_db())

                            case self.db.table_history.uri:
                                self.db.table_history.delete(selection, selection_argument)

                            case self.db.table_zwave_history.uri:
                                self.db.table_zwave_history.delete(selection, selection_argument)

                            case self.db.table_doorlock.uri:
                                self.db.table_doorlock.delete(selection, selection_argument)
                                self._controller.state.sync_automation_devices_data(self.get_automation_devices_from_db())

                            case self.db.table_dimmer.uri:
                                self.db.table_dimmer.delete(selection, selection_argument)
                                self._controller.state.sync_automation_devices_data(self.get_automation_devices_from_db())

                            case self.db.table_thermostat.uri:
                                self.db.table_thermostat.delete(selection, selection_argument)
                                self._controller.state.sync_automation_devices_data(self.get_automation_devices_from_db())

                            case self.db.table_zwave_node.uri:
                                self.db.table_zwave_node.delete(selection, selection_argument)
                                self._controller.state.sync_automation_devices_data(self.get_automation_devices_from_db())

                            case self.db.table_automation.uri:
                                self.db.table_automation.delete(selection, selection_argument)
                                self._controller.state.sync_automation_devices_data(self.get_automation_devices_from_db())

                            case self.db.table_partition.uri:
                                self.db.table_partition.delete(selection, selection_argument)
                                self._controller.state.sync_partitions_data(self.get_partitions_from_db())

                            case self.db.table_user.uri:
                                self.db.table_user.delete(selection, selection_argument)

                            case self.db.table_dashboard_msgs.uri:
                                self.db.table_dashboard_msgs.delete(selection, selection_argument)

                            case self.db.table_eu_event.uri:
                                self.db.table_eu_event.delete(selection, selection_argument)

                            case self.db.table_powerg_device.uri:
                                self.db.table_powerg_device.delete(selection, selection_argument)

                            case self.db.table_weather.uri:
                                self.db.table_weather.delete(selection, selection_argument)
                                self._controller.state.sync_weather_data(self.get_weather_from_db())

                            case self.db.table_zwave_association_goup.uri:
                                self.db.table_zwave_association_goup.delete(selection, selection_argument)

                            case self.db.table_virtual_device.uri:
                                self.db.table_virtual_device.delete(selection, selection_argument)
                                self._controller.state.sync_automation_devices_data(self.get_automation_devices_from_db())

                            case self.db.table_zwave_other.uri:
                                self.db.table_zwave_other.delete(selection, selection_argument)
                                self._controller.state.sync_automation_devices_data(self.get_automation_devices_from_db())

                            case self.db.table_output_rules.uri:
                                self.db.table_output_rules.delete(selection, selection_argument)

                            case _:
                                LOGGER.debug("iq2meid deleting unknown uri:%s", uri)
                                LOGGER.debug(data)

                    case "insert":
                        content_values = data.get("contentValues", {})

                        match uri:
                            # Inser State Content Provider
                            case self.db.table_state.uri:
                                self.db.table_state.insert(data=content_values)

                                name = content_values.get("name", "")
                                new_value = content_values.get("value", "")
                                if name in self.state_partition:
                                    partition_id = content_values.get("partition_id", "")
                                    partition = self._controller.state.partition(partition_id)
                                    if partition is not None:
                                        match name:
                                            case "ALARM_STATE":
                                                partition.alarm_state = PartitionAlarmState(new_value)

                            # Inser Partition Content Provider
                            case self.db.table_partition.uri:
                                self.db.table_partition.insert(data=content_values)
                                self._controller.state.sync_partitions_data(self.get_partitions_from_db())

                            # Insert Settings Content Provider
                            case self.db.table_qolsyssettings.uri:
                                self.db.table_qolsyssettings.insert(data=content_values)
                                # Update Partition setting - Send notification if setting has changed
                                name = content_values.get("name", "")
                                new_value = content_values.get("value", "")
                                if name in self.settings_partition:
                                    partition_id = content_values.get("partition_id", "")
                                    partition = self._controller.state.partition(partition_id)
                                    if partition is not None:
                                        match name:
                                            case "SYSTEM_STATUS":
                                                partition.system_status = PartitionSystemStatus(new_value)
                                            case "SYSTEM_STATUS_CHANGED_TIME":
                                                partition.system_status_changed_time = new_value
                                            case "EXIT_SOUNDS":
                                                partition.exit_sounds = new_value
                                            case "ENTRY_DELAYS":
                                                partition.entry_delays = new_value

                            # UserContentProvider
                            case self.db.table_user.uri:
                                self.db.table_user.insert(data=content_values)
                                # No action needed

                            # MasterSlave Content Provider
                            case self.db.table_master_slave.uri:
                                self.db.table_master_slave.insert(data=content_values)
                                # No action needed

                            # Automation Content Provider
                            case self.db.table_automation.uri:
                                self.db.table_automation.insert(content_values)
                                # No action needed

                            # Sensor Content Provider
                            case self.db.table_sensor.uri:
                                self.db.table_sensor.insert(data=content_values)
                                self._controller.state.sync_zones_data(self.get_zones_from_db())

                            # Door Lock Content Provider
                            case self.db.table_doorlock.uri:
                                self.db.table_doorlock.insert(data=content_values)
                                self._controller.state.sync_automation_devices_data(self.get_automation_devices_from_db())

                            # Dimmer Content Provider
                            case self.db.table_dimmer.uri:
                                self.db.table_dimmer.insert(data=content_values)
                                self._controller.state.sync_automation_devices_data(self.get_automation_devices_from_db())

                            # Thermostat Content Provider
                            case self.db.table_thermostat.uri:
                                self.db.table_thermostat.insert(data=content_values)
                                self._controller.state.sync_automation_devices_data(self.get_automation_devices_from_db())

                            # ZWave Node Content Provider
                            case self.db.table_zwave_node.uri:
                                self.db.table_zwave_node.insert(data=content_values)
                                self._controller.state.sync_automation_devices_data(self.get_automation_devices_from_db())

                            # HistoryContentProvider
                            case self.db.table_history.uri:
                                self.db.table_history.insert(data=content_values)

                            # AlarmedSensorProvider
                            case self.db.table_alarmedsensor.uri:
                                partition_id = content_values.get("partition_id", "")
                                self.db.table_alarmedsensor.insert(data=content_values)

                                partition = self._controller.state.partition(partition_id)
                                if partition is not None:
                                    # Add new alarm type to partition
                                    try:
                                        partition.append_alarm_type([PartitionAlarmType(content_values.get("sgroup", ""))])
                                    except ValueError:
                                        LOGGER.error("PLEASE REPORT: Unknown alarm type: %s", content_values.get("sgroup", ""))
                                        partition.append_alarm_type([PartitionAlarmType.EMPTY])

                            # IQRemoteSettingsProvider
                            case self.db.table_iqremotesettings.uri:
                                self.db.table_iqremotesettings.insert(data=content_values)

                            # HeatMapContentProvider
                            case self.db.table_heat_map.uri:
                                self.db.table_heat_map.insert(data=content_values)

                            # ZDeviceHistoryContentProvider
                            case self.db.table_zwave_history.uri:
                                self.db.table_zwave_history.insert(data=content_values)

                            # Dashboard Message Content Provider
                            case self.db.table_dashboard_msgs.uri:
                                self.db.table_dashboard_msgs.insert(data=content_values)

                            # EU_EVENT
                            case self.db.table_eu_event.uri:
                                self.db.table_eu_event.insert(data=content_values)

                            # PowerG Device
                            case self.db.table_powerg_device.uri:
                                self.db.table_powerg_device.insert(data=content_values)

                            # Weather
                            case self.db.table_weather.uri:
                                self.db.table_weather.insert(data=content_values)
                                self._controller.state.sync_weather_data(self.get_weather_from_db())

                            # ZWave Association Group
                            case self.db.table_zwave_association_goup.uri:
                                self.db.table_zwave_association_goup.insert(data=content_values)

                            # Zwave Other
                            case self.db.table_zwave_other.uri:
                                self.db.table_zwave_other.insert(data=content_values)
                                self._controller.state.sync_automation_devices_data(self.get_automation_devices_from_db())

                            # Virtual Device
                            case self.db.table_virtual_device.uri:
                                self.db.table_virtual_device.insert(data=content_values)
                                self._controller.state.sync_automation_devices_data(self.get_automation_devices_from_db())

                            # Output Rules
                            case self.db.table_output_rules.uri:
                                self.db.table_output_rules.insert(data=content_values)

                            case _:
                                LOGGER.debug("iq2meid inserting unknow uri:%s", uri)
                                LOGGER.debug(data)

                    case _:
                        LOGGER.debug("iq2meid - Unknow dboperation: %s", dbOperation)
                        LOGGER.debug(data)
            case _:
                LOGGER.debug("iq2meid - Unknow event: %s", eventName)
                LOGGER.debug(data)

    def check_user(self, user_code: str) -> int:
        for user in self._users:
            if user.user_code == user_code:
                return user.id

        # No valid user code found
        return -1

    def get_automation_devices_from_db(self) -> list[QolsysAutomationDevice]:
        allowed_protocols = [
            AutomationDeviceProtocol.POWERG,
            AutomationDeviceProtocol.ZIGBEE,
            AutomationDeviceProtocol.ZWAVE,
            AutomationDeviceProtocol.ADC,
        ]

        automation_devices: list[QolsysAutomationDevice] = []
        devices_list = self.db.get_automation_devices()

        # Add all device in automation content provider table
        for device in devices_list:
            try:
                protocol = AutomationDeviceProtocol(device.get("protocol", ""))
            except ValueError:
                protocol = AutomationDeviceProtocol.UNKNOWN

            new_device: QolsysAutomationDevice | None = None

            match protocol:
                case AutomationDeviceProtocol.POWERG:
                    new_device = QolsysAutomationDevicePowerG(self._controller, device)

                case AutomationDeviceProtocol.ZWAVE:
                    node_id = device.get("virtual_node_id", "")
                    zwave_node = self.db.get_zwave_device(node_id)
                    if zwave_node is not None:
                        new_device = QolsysAutomationDeviceZwave(self._controller, zwave_node, device)

                case AutomationDeviceProtocol.ZIGBEE:
                    new_device = QolsysAutomationDeviceZigbee(self._controller, device)

                case _:
                    LOGGER.debug("Unknown protocol for automation device: %s", protocol)
                    LOGGER.debug(device)

            if new_device is not None and protocol in allowed_protocols:
                automation_devices.append(new_device)

        # Add other Z-Wave devices that are not in automation content provider
        if AutomationDeviceProtocol.ZWAVE in allowed_protocols:
            for zwave_device in self.db.get_zwave_devices():
                node_type = zwave_device.get("node_type", "")

                if node_type in [
                    "Energy Clamp",
                    "Thermometer",
                    "External Siren",
                    "Garage Door",
                    "Repeater",
                    "Smart Socket",
                    "Water Valve",
                ]:
                    zwave_id = zwave_device.get("node_id", "")
                    if not zwave_id:
                        LOGGER.debug("Skipping Z-Wave device with empty node_id")
                        continue

                    if any(d.virtual_node_id == zwave_id for d in automation_devices):
                        LOGGER.debug(
                            "AutDev%s: Z-Wave device with the same virtual_node_id already exists, skipping", zwave_id
                        )
                        continue

                    new_zwave_device = QolsysAutomationDeviceZwave(self._controller, zwave_device, {})
                    new_zwave_device.virtual_node_id = zwave_id
                    new_zwave_device.device_type = node_type
                    automation_devices.append(new_zwave_device)

        # Add virtual adc devices
        if AutomationDeviceProtocol.ADC in allowed_protocols:
            adc_devices = self.db.get_adc_devices()
            for adc_device in adc_devices:
                adc_id = adc_device.get("device_id", "")
                if not adc_id:
                    LOGGER.debug("Skipping ADC device with empty device_id")
                    continue

                if any(d.virtual_node_id == adc_id for d in automation_devices):
                    LOGGER.debug("AutDev%s: ADC device with the same virtual_node_id already exists, skipping", adc_id)
                    continue

                new_adc_device = QolsysAutomationDeviceADC(self._controller, adc_device)
                automation_devices.append(new_adc_device)

        return automation_devices

    def get_scenes_from_db(self) -> list[QolsysScene]:
        scenes = []
        scenes_list: list[dict[str, str]] = self.db.get_scenes()

        # Create scenes array
        for scene_info in scenes_list:
            scenes.append(QolsysScene(scene_info))

        return scenes

    def get_weather_from_db(self) -> QolsysWeather:
        weather = QolsysWeather()
        forecast_dic_list: list[dict[str, str]] = self.db.get_weather()

        forecast_obj_list = []
        for forecast in forecast_dic_list:
            forecast_obj_list.append(QolsysForecast(forecast))

        # Create weather array
        weather.update(forecast_obj_list)

        return weather

    def get_zones_from_db(self) -> list[QolsysZone]:
        zones = []
        zones_list: list[dict[str, str]] = self.db.get_zones()

        # Create sensors array
        for zone_info in zones_list:
            new_zone = QolsysZone(zone_info, self._controller.settings)

            if new_zone.current_capability == "POWERG":
                powerg_dict = self.db.get_powerg(short_id=new_zone.shortID)
                if powerg_dict is not None:
                    new_zone.update_powerg(powerg_dict)

            zones.append(new_zone)

        return zones

    def get_partitions_from_db(self) -> list[QolsysPartition]:
        partitions = []
        partition_list: list[dict[str, str]] = self.db.get_partitions()

        # Create partitions array
        for partition_dict in partition_list:
            partition_id = partition_dict["partition_id"]

            settings_dict = {
                "SYSTEM_STATUS": self.db.get_setting_partition("SYSTEM_STATUS", partition_id) or "UNKNOWN",
                "SYSTEM_STATUS_CHANGED_TIME": self.db.get_setting_partition("SYSTEM_STATUS_CHANGED_TIME", partition_id) or "",
                "EXIT_SOUNDS": self.db.get_setting_partition("EXIT_SOUNDS", partition_id) or "",
                "ENTRY_DELAYS": self.db.get_setting_partition("ENTRY_DELAYS", partition_id) or "",
            }

            alarm_type = []
            for alarm in self.db.get_alarm_type(partition_id):
                alarm_type.append(PartitionAlarmType(alarm))

            alarm_state = PartitionAlarmState(self.db.get_state_partition("ALARM_STATE", partition_id) or "UNKNOWN")

            quick_exit_state = PartitionQuickExitState(self.db.get_state_partition("QUICK_EXIT_STATE", partition_id) or "None")

            partition = QolsysPartition(
                self._controller, partition_dict, settings_dict, alarm_state, alarm_type, quick_exit_state
            )
            partitions.append(partition)

        return partitions

    def to_event_dict(self) -> dict[str, str]:
        return {
            "product_type": self.product_type.name,
            "hardware_version": self.HARDWARE_VERSION,
            "mac_address": self.MAC_ADDRESS,
            "panel_tamper_state": self.PANEL_TAMPER_STATE,
            "ac_status": self.AC_STATUS,
            "battery_status": self.BATTERY_STATUS,
            "fail_to_communicate": self.FAIL_TO_COMMUNICATE,
            "country": self.COUNTRY,
            "language": self.LANGUAGE,
            "temp_format": self.TEMPFORMAT,
            "zwave_firmware_version": self.ZWAVE_FIRM_WARE_VERSION,
            "zwave_card": self.ZWAVE_CARD,
            "zwave_controller": self.ZWAVE_CONTROLLER,
            "partitions": self.PARTITIONS,
            "control_4": self.CONTROL_4,
            "six_digit_user_code": self.SIX_DIGIT_USER_CODE,
            "secure_arming": self.SECURE_ARMING,
            "auto_stay": self.AUTO_STAY,
            "auto_bypass": self.AUTO_BYPASS,
            "auto_arm_stay": self.AUTO_ARM_STAY,
            "auto_exit_extension": self.AUTO_EXIT_EXTENSION,
            "final_exit_door_arming": self.FINAL_EXIT_DOOR_ARMING,
            "no_arm_low_battery": self.NO_ARM_LOW_BATTERY,
            "timer_normal_entry_delay": self.TIMER_NORMAL_ENTRY_DELAY,
            "timer_normal_exit_delay": self.TIMER_NORMAL_EXIT_DELAY,
            "timer_long_entry_delay": self.TIMER_LONG_ENTRY_DELAY,
            "timer_long_exit_delay": self.TIMER_LONG_EXIT_DELAY,
            "auxiliary_panic_enabled": self.AUXILIARY_PANIC_ENABLED,
            "fire_panic_enabled": self.FIRE_PANIC_ENABLED,
            "police_panic_enabled": self.POLICE_PANIC_ENABLED,
            "nightmode_settings": self.NIGHTMODE_SETTINGS,
            "night_settings_state": self.NIGHT_SETTINGS_STATE,
            "show_security_sensors": self.SHOW_SECURITY_SENSORS,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    def dump(self) -> None:
        LOGGER.debug("*** Qolsys Panel Information ***")
        LOGGER.debug("Product Type: %s", self.product_type.name)
        LOGGER.debug("Hardware Version: %s", self.HARDWARE_VERSION)
        LOGGER.debug("MAC Address: %s", self.MAC_ADDRESS)
        LOGGER.debug("Unique ID: %s", self.unique_id)
        LOGGER.debug("Panel Tamper State: %s", self.PANEL_TAMPER_STATE)
        LOGGER.debug("AC Status: %s", self.AC_STATUS)
        LOGGER.debug("Battery Status: %s", self.BATTERY_STATUS)
        LOGGER.debug("Fail To Communicate: %s", self.FAIL_TO_COMMUNICATE)
        LOGGER.debug("Country: %s", self.COUNTRY)
        LOGGER.debug("Language: %s", self.LANGUAGE)
        LOGGER.debug("Temp Format: %s", self.TEMPFORMAT)
        LOGGER.debug("Z-Wave Firmware Version: %s", self.ZWAVE_FIRM_WARE_VERSION)
        LOGGER.debug("Z-Wave Card Present: %s", self.ZWAVE_CARD)
        LOGGER.debug("Z-Wave Controller Enabled: %s", self.ZWAVE_CONTROLLER)
        LOGGER.debug("Partitions Enabled: %s", self.PARTITIONS)
        LOGGER.debug("Control4 Enabled: %s", self.CONTROL_4)
        LOGGER.debug("Six Digit User Code Enabled: %s", self.SIX_DIGIT_USER_CODE)
        LOGGER.debug("Secure Arming: %s", self.SECURE_ARMING)
        LOGGER.debug("Auto-Stay: %s", self.AUTO_STAY)
        LOGGER.debug("Auto-Bypass: %s", self.AUTO_BYPASS)
        LOGGER.debug("Auto-Arm-Stay: %s", self.AUTO_ARM_STAY)
        LOGGER.debug("Auto-Exit-Extension: %s", self.AUTO_EXIT_EXTENSION)
        LOGGER.debug("Final-Exit-Door-Arming: %s", self.FINAL_EXIT_DOOR_ARMING)
        LOGGER.debug("No-Arm-Low-Battery: %s", self.NO_ARM_LOW_BATTERY)
        LOGGER.debug("Normal Entry Delay: %s", self.TIMER_NORMAL_ENTRY_DELAY)
        LOGGER.debug("Normal Exit Delay: %s", self.TIMER_NORMAL_EXIT_DELAY)
        LOGGER.debug("Long Entry Delay: %s", self.TIMER_LONG_ENTRY_DELAY)
        LOGGER.debug("Long Exit Delay: %s", self.TIMER_LONG_EXIT_DELAY)
        LOGGER.debug("Auxiliary Panic Enabled: %s", self.AUXILIARY_PANIC_ENABLED)
        LOGGER.debug("Fire Panic Enabled: %s", self.FIRE_PANIC_ENABLED)
        LOGGER.debug("Police Panic Enabled: %s", self.POLICE_PANIC_ENABLED)
        LOGGER.debug("Night Mode Settings: %s", self.NIGHTMODE_SETTINGS)
        LOGGER.debug("Night Mode Settings Stage: %s", self.NIGHT_SETTINGS_STATE)
        LOGGER.debug("Show Security Sensors: %s", self.SHOW_SECURITY_SENSORS)
        LOGGER.debug("Safety Sensor Quick Exit: %s", self.SAFETY_SENSOR_QUICK_EXIT)

        LOGGER.debug("Users list:")
        for user in self._users:
            LOGGER.debug("User: %s", user.id)

        LOGGER.debug("*** Plugin Information ***")
        LOGGER.debug("Motion Delay Enabled: %s", self._controller.settings.motion_sensor_delay)
        LOGGER.debug("Motion Delay Value: %s", self._controller.settings.motion_sensor_delay_sec)
