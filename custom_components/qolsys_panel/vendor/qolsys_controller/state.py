from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .automation.device import QolsysAutomationDevice
from .automation_adc.device import QolsysAutomationDeviceADC
from .automation_zwave.device import QolsysAutomationDeviceZwave
from .enum_qolsys import QolsysNotification
from .observable import Event, QolsysObservable

from .weather import QolsysWeather

LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .controller import QolsysController

    from .partition import QolsysPartition
    from .scene import QolsysScene
    from .zone import QolsysZone


class QolsysState(QolsysObservable):
    def __init__(self, controller: QolsysController) -> None:
        super().__init__()
        self._controller: QolsysController = controller
        self._weather: QolsysWeather = QolsysWeather()
        self._partitions: list[QolsysPartition] = []
        self._zones: list[QolsysZone] = []
        self._automation_devices: list[QolsysAutomationDevice] = []
        self._scenes: list[QolsysScene] = []

    @property
    def partitions(self) -> list[QolsysPartition]:
        return self._partitions

    @property
    def automation_devices(self) -> list[QolsysAutomationDevice]:
        return self._automation_devices

    @property
    def zones(self) -> list[QolsysZone]:
        return self._zones

    @property
    def scenes(self) -> list[QolsysScene]:
        return self._scenes

    @property
    def weather(self) -> QolsysWeather:
        return self._weather

    def partition(self, partition_id: str) -> QolsysPartition | None:
        for partition in self.partitions:
            if partition.id == partition_id:
                return partition

        return None

    def partition_add(self, new_partition: QolsysPartition) -> None:
        for partition in self.partitions:
            if new_partition.id == partition.id:
                LOGGER.debug(
                    "Adding Partition to State, Partition%s (%s) - Already in Partitions List",
                    new_partition.id,
                    partition.name,
                )
                return

        self.partitions.append(new_partition)
        self.partitions.sort(key=lambda x: x.id, reverse=False)
        self.notify(Event(QolsysNotification.PARTITION_ADD, self, new_partition.to_dict_event()))

    def partition_delete(self, partition_id: str) -> None:
        partition = self.partition(partition_id)

        if partition is None:
            LOGGER.debug("Deleting Partition from State, Partition%s not found", partition_id)
            return

        self.partitions.remove(partition)
        self.notify(Event(QolsysNotification.PARTITION_DELETE, self, partition.to_dict_event()))

    def scene(self, scene_id: str) -> QolsysScene | None:
        for scene in self.scenes:
            if scene.scene_id == scene_id:
                return scene

        return None

    def scene_add(self, new_scene: QolsysScene) -> None:
        for scene in self.scenes:
            if new_scene.scene_id == scene.scene_id:
                LOGGER.debug("Adding Scene to State, Scene%s (%s) - Already in Scene List", new_scene.scene_id, scene.name)
                return

        self.scenes.append(new_scene)
        self.scenes.sort(key=lambda x: x.scene_id, reverse=False)
        self.notify(Event(QolsysNotification.SCENE_ADD, self, new_scene.to_dict_event()))

    def scene_delete(self, scene_id: str) -> None:
        scene = self.scene(scene_id)

        if scene is None:
            LOGGER.debug("Deleting Scene from State, Scene%s not found", scene_id)
            return

        self.scenes.remove(scene)
        self.notify(Event(QolsysNotification.SCENE_DELETE, self, scene.to_dict_event()))

    def automation_device(self, virtual_node_id: str) -> QolsysAutomationDevice | None:
        for automation_device in self.automation_devices:
            if automation_device.virtual_node_id == virtual_node_id:
                return automation_device
        return None

    def automation_device_add(self, new_automation_device: QolsysAutomationDevice) -> None:
        for automation_device in self.automation_devices:
            if new_automation_device.virtual_node_id == automation_device.virtual_node_id:
                LOGGER.debug(
                    "Adding AutomationDevice to State, AutDev%s (%s) - Already in AutomationDevice List",
                    new_automation_device.virtual_node_id,
                    automation_device.device_name,
                )
                return

        self.automation_devices.append(new_automation_device)
        self.automation_devices.sort(key=lambda x: x.virtual_node_id, reverse=False)
        self.notify(Event(QolsysNotification.AUTOMATION_ADD, self, new_automation_device.to_dict_event()))

    def automation_device_delete(self, virtual_node_id: str) -> None:
        automation_device = self.automation_device(virtual_node_id)

        if automation_device is None:
            LOGGER.debug("Deleting AutomationDevice from State, AutDev%s not found", virtual_node_id)
            return

        self.automation_devices.remove(automation_device)
        self.notify(Event(QolsysNotification.AUTOMATION_DELETE, self, automation_device.to_dict_event()))

    def zone(self, zone_id: str) -> QolsysZone | None:
        for zone in self.zones:
            if zone.zone_id == zone_id:
                return zone
        return None

    def zone_from_short_id(self, short_id: int) -> QolsysZone | None:
        for zone in self.zones:
            if zone.shortID == str(short_id):
                return zone
        return None

    def zone_add(self, new_zone: QolsysZone) -> None:
        for zone in self.zones:
            if new_zone.zone_id == zone.zone_id:
                LOGGER.debug("Adding Zone to State, zone%s (%s) - Already in Zone List", new_zone.zone_id, new_zone.sensorname)
                return

        self.zones.append(new_zone)
        self.zones.sort(key=lambda x: x.zone_id, reverse=False)
        self.notify(Event(QolsysNotification.ZONE_ADD, self, new_zone.to_dict_event()))

    def zone_delete(self, zone_id: str) -> None:
        zone = self.zone(zone_id)

        if zone is None:
            LOGGER.debug("Deleting Zone from State, Zone%s not found", zone_id)
            return

        self.zones.remove(zone)
        self.notify(Event(QolsysNotification.ZONE_DELETE, self, zone.to_dict_event()))

    def sync_automation_devices_data(self, db_automation_devices: list[QolsysAutomationDevice]) -> None:
        db_automation_list = []
        for db_automation in db_automation_devices:
            db_automation_list.append(db_automation.virtual_node_id)

        state_automation_list = []
        for state_automation in self.automation_devices:
            state_automation_list.append(state_automation.virtual_node_id)

        # Update existing Automation Devices
        for state_automation in self.automation_devices:
            if state_automation.virtual_node_id in db_automation_list:
                for db_automation in db_automation_devices:
                    if state_automation.virtual_node_id == db_automation.virtual_node_id:
                        # Update ADC extracted attributes
                        if isinstance(state_automation, QolsysAutomationDeviceADC) and isinstance(
                            db_automation, QolsysAutomationDeviceADC
                        ):
                            state_automation.update_adc_device(db_automation.to_dict_adc())

                        # Update Z-Wave extra attributes
                        if isinstance(state_automation, QolsysAutomationDeviceZwave) and isinstance(
                            db_automation, QolsysAutomationDeviceZwave
                        ):
                            state_automation.update_zwave_device(db_automation.to_dict_zwave())

                        # Update Automation Device base attributes
                        state_automation.update_automation_device(db_automation.to_dict())

                        LOGGER.debug("sync_data - update AutDev%s", state_automation.virtual_node_id)
                        break

        # Add new Automation Devices
        for db_automation in db_automation_devices:
            if db_automation.virtual_node_id not in state_automation_list:
                LOGGER.debug("sync_data - add AutDev%s", db_automation.virtual_node_id)
                self.automation_device_add(db_automation)

        # Delete Automation Device
        for state_automation in list(self.automation_devices):
            if state_automation.virtual_node_id not in db_automation_list:
                LOGGER.debug("sync_data - delete AutDev%s", state_automation.virtual_node_id)
                self.automation_device_delete(state_automation.virtual_node_id)

    def sync_weather_data(self, db_weather: QolsysWeather) -> None:
        LOGGER.debug("sync_data - update Weather")
        self._weather.update(db_weather.forecasts)

    def sync_scenes_data(self, db_scenes: list[QolsysScene]) -> None:
        db_scene_list = []
        for db_scene in db_scenes:
            db_scene_list.append(db_scene.scene_id)

        state_scene_list = []
        for state_scene in self.scenes:
            state_scene_list.append(state_scene.scene_id)

        # Update existing scenes
        for state_scene in self.scenes:
            if state_scene.scene_id in db_scene_list:
                for db_scene in db_scenes:
                    if state_scene.scene_id == db_scene.scene_id:
                        LOGGER.debug("sync_data - update Scene%s", state_scene.scene_id)
                        state_scene.update(db_scene.to_dict())
                        break

        # Delete scenes
        for state_scene in list(self.scenes):
            if state_scene.scene_id not in db_scene_list:
                LOGGER.debug("sync_data - delete Scene%s", state_scene.scene_id)
                self.scene_delete(state_scene.scene_id)

        # Add new scene
        for db_scene in db_scenes:
            if db_scene.scene_id not in state_scene_list:
                LOGGER.debug("sync_data - add Scene%s", db_scene.scene_id)
                self.scene_add(db_scene)

    def sync_zones_data(self, db_zones: list[QolsysZone]) -> None:
        db_zone_list = []
        for db_zone in db_zones:
            db_zone_list.append(db_zone.zone_id)

        state_zone_list = []
        for state_zone in self.zones:
            state_zone_list.append(state_zone.zone_id)

        # Update existing zones
        for state_zone in self.zones:
            if state_zone.zone_id in db_zone_list:
                for db_zone in db_zones:
                    if state_zone.zone_id == db_zone.zone_id:
                        LOGGER.debug("sync_data - update Zone%s", state_zone.zone_id)
                        state_zone.update(db_zone.to_dict())
                        state_zone.update_powerg(db_zone.to_powerg_dict())
                        break

        # Delete zones
        for state_zone in list(self.zones):
            if state_zone.zone_id not in db_zone_list:
                LOGGER.debug("sync_data - delete Zone%s", state_zone.zone_id)
                self.zone_delete(state_zone.zone_id)

        # Add new zone
        for db_zone in db_zones:
            if db_zone.zone_id not in state_zone_list:
                LOGGER.debug("sync_data - add Zone%s", db_zone.zone_id)
                self.zone_add(db_zone)

    def sync_partitions_data(self, db_partitions: list[QolsysPartition]) -> None:
        db_partition_list = []
        for db_partition in db_partitions:
            db_partition_list.append(db_partition.id)

        state_partition_list = []
        for state_partition in self.partitions:
            state_partition_list.append(state_partition.id)

        # Update existing partitions
        for state_partition in self.partitions:
            if state_partition.id in db_partition_list:
                for db_partition in db_partitions:
                    if state_partition.id == db_partition.id:
                        LOGGER.debug("sync_data - update Partition%s", state_partition.id)
                        state_partition.update_partition(db_partition.to_dict_partition())
                        state_partition.update_settings(db_partition.to_dict_settings())
                        state_partition.alarm_type_array = db_partition.alarm_type_array
                        state_partition.alarm_state = db_partition.alarm_state
                        state_partition.quick_exit_state = db_partition.quick_exit_state
                        state_partition.quick_exit_delay = db_partition.quick_exit_delay
                        state_partition.quick_exit_start_time = db_partition.quick_exit_start_time
                        break

        # Delete partitions
        for state_partition in list(self.partitions):
            if state_partition.id not in db_partition_list:
                LOGGER.debug("sync_data - delete Partition%s", state_partition.id)
                self.partition_delete(state_partition.id)

        # Add new partition
        for db_partition in db_partitions:
            if db_partition.id not in state_partition_list:
                LOGGER.debug("sync_data - add Partition%s", db_partition.id)
                self.partition_add(db_partition)

    def dump(self) -> None:  # noqa: PLR0912, PLR0915
        LOGGER.debug("*** Device Information ***")

        for partition in self.partitions:
            pid = partition.id
            name = partition.name
            LOGGER.debug("Partition%s (%s) - system_status: %s", pid, name, partition.system_status)
            LOGGER.debug("Partition%s (%s) - alarm_state: %s", pid, name, partition.alarm_state)

            if partition.alarm_type_array == []:
                LOGGER.debug("Partition%s (%s) - alarm_type: %s", pid, name, "None")
            else:
                for alarm_type in partition.alarm_type_array:
                    LOGGER.debug("Partition%s (%s) - alarm_type: %s", pid, name, alarm_type)

            LOGGER.debug("Partition%s (%s) - exit_sounds: %s", pid, name, partition.exit_sounds)
            LOGGER.debug("Partition%s (%s) - entry_delays: %s", pid, name, partition.entry_delays)
            LOGGER.debug("Partition%s (%s) - quick_exit_state: %s", pid, name, partition.quick_exit_state)

        for zone in self.zones:
            zid = zone.zone_id
            name = zone.sensorname
            LOGGER.debug("Zone%s (%s) - status: %s", zid, name, zone.sensorstatus)
            LOGGER.debug("Zone%s (%s) - battery_status: %s", zid, name, zone.battery_status)

            if zone.latestdBm is not None:
                LOGGER.debug("Zone%s (%s) - latestdBm: %s", zid, name, zone.latestdBm)

            if zone.averagedBm is not None:
                LOGGER.debug("Zone%s (%s) - averagedBm: %s", zid, name, zone.averagedBm)

            if zone.is_powerg_temperature_enabled():
                LOGGER.debug("Zone%s (%s) - powerg_temperature: %s", zid, name, zone.powerg_temperature)

            if zone.is_powerg_light_enabled():
                LOGGER.debug("Zone%s (%s) - powerg_light: %s", zid, name, zone.powerg_light)

        for automation_device in self.automation_devices:
            LOGGER.debug("%s - %s", automation_device.prefix, automation_device.device_type)

            for endpoint, services_list in automation_device.services.items():
                for service in services_list:
                    for line in service.info():
                        LOGGER.debug(line)

        for scene in self.scenes:
            sid = scene.scene_id
            name = scene.name
            LOGGER.debug("Scene%s (%s)", sid, name)

        for forecast in self.weather.forecasts:
            LOGGER.debug(
                "Weather - %s - High: %s, Low:%s, Condition: %s",
                forecast.day_of_week[0:3],
                forecast.high_temp,
                forecast.low_temp,
                forecast.condition,
            )
