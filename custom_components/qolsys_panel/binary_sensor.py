"""Support for Qolsys Panel binary sensors."""

from __future__ import annotations

from qolsys_controller import qolsys_controller
from qolsys_controller.enum import PartitionAlarmType, ZoneSensorType, ZoneStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import QolsysPanelConfigEntry
from .entity import (
    QolsysPanelSensorEntity,
    QolsysPartitionEntity,
    QolsysZoneEntity,
    QolsysZwaveEntity,
)

PANEL_SENSOR = [
    BinarySensorEntityDescription(
        key="AC_STATUS",
        entity_registry_enabled_default=True,
        translation_key="panel_ac_status",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    BinarySensorEntityDescription(
        key="PANEL_TAMPER_STATE",
        translation_key="panel_tamper_state",
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.TAMPER,
    ),
    BinarySensorEntityDescription(
        key="BATTERY_STATUS",
        translation_key="panel_battery_status",
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.BATTERY,
    ),
    BinarySensorEntityDescription(
        key="FAIL_TO_COMMUNICATE",
        translation_key="panel_fail_to_communicate",
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key="GSM_CONNECTION_STATUS",
        translation_key="panel_gsm_connection_status",
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key="ZWAVE_CONTROLLER",
        translation_key="panel_zwave_controller",
        entity_registry_enabled_default=True,
    ),
    BinarySensorEntityDescription(
        key="SECURE_ARMING",
        translation_key="panel_secure_arming",
        entity_registry_enabled_default=True,
    ),
    BinarySensorEntityDescription(
        key="AUTO_STAY",
        translation_key="panel_auto_stay",
        entity_registry_enabled_default=True,
    ),
    BinarySensorEntityDescription(
        key="AUTO_ARM_STAY",
        translation_key="panel_auto_arm_stay",
        entity_registry_enabled_default=True,
    ),
    BinarySensorEntityDescription(
        key="CONTROL_4",
        translation_key="panel_control_4",
        entity_registry_enabled_default=True,
    ),
    BinarySensorEntityDescription(
        key="AUTO_BYPASS",
        translation_key="panel_auto_bypass",
        entity_registry_enabled_default=True,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    entities: list[BinarySensorEntity] = []
    QolsysPanel = config_entry.runtime_data

    for zone in QolsysPanel.state.zones:
        entities.append(ZonesSensor(QolsysPanel, zone.zone_id, config_entry.unique_id))
        entities.append(
            ZoneSensor_Unreachable(QolsysPanel, zone.zone_id, config_entry.unique_id)
        )
        entities.append(
            ZoneSensor_Tamper(QolsysPanel, zone.zone_id, config_entry.unique_id)
        )

        if zone.is_battery_enabled():
            entities.append(
                ZoneSensor_BatteryStatus(
                    QolsysPanel, zone.zone_id, config_entry.unique_id
                )
            )

        if zone.is_ac_enabled():
            entities.append(
                ZoneSensor_ACStatus(QolsysPanel, zone.zone_id, config_entry.unique_id)
            )

    for sensor in PANEL_SENSOR:
        entities.append(PanelSensor(QolsysPanel, config_entry.unique_id, sensor))

    for partition in QolsysPanel.state.partitions:
        entities.append(
            PartitionAlarmSensor(
                QolsysPanel, partition.id, config_entry.unique_id, "Police"
            )
        )
        entities.append(
            PartitionAlarmSensor(
                QolsysPanel, partition.id, config_entry.unique_id, "Fire"
            )
        )
        entities.append(
            PartitionAlarmSensor(
                QolsysPanel, partition.id, config_entry.unique_id, "Auxiliary"
            )
        )
        entities.append(
            PartitionExitSoundSensor(QolsysPanel, partition.id, config_entry.unique_id)
        )
        entities.append(
            PartitionEntryDelaySensor(QolsysPanel, partition.id, config_entry.unique_id)
        )

    # Add Z-Wave device status sensor
    for device in QolsysPanel.state.zwave_devices:
        entities.append(
            ZwaveDevice_Status(QolsysPanel, device.node_id, config_entry.unique_id)
        )

    async_add_entities(entities)


class PartitionExitSoundSensor(QolsysPartitionEntity, BinarySensorEntity):
    """A binary sensor entity for partition exit sound."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, QolsysPanel: qolsys_controller, partition_id: int, unique_id: str
    ) -> None:
        """Binary sensor entity for partition exit sound status."""
        super().__init__(QolsysPanel, partition_id, unique_id)
        self._attr_unique_id = f"{self._partition_unique_id}_panel_exit_sounds"
        self._attr_translation_key = "partition_exit_sounds"

    @property
    def is_on(self) -> bool:
        """Return if this partition exit sound is on."""
        return self._partition.exit_sounds == "ON"


class PartitionEntryDelaySensor(QolsysPartitionEntity, BinarySensorEntity):
    """A binary sensor entity for partition entry delay."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, QolsysPanel: qolsys_controller, partition_id: int, unique_id: str
    ) -> None:
        """Set up a binary sensor entity partition entry delay."""
        super().__init__(QolsysPanel, partition_id, unique_id)
        self._attr_unique_id = f"{self._partition_unique_id}_panel_entry_delays"
        self._attr_translation_key = "partition_entry_delays"

    @property
    def is_on(self) -> bool:
        """Return if this partition entry delay is on."""
        return self._partition.entry_delays == "ON"


class PartitionAlarmSensor(QolsysPartitionEntity, BinarySensorEntity):
    """A binary sensor entity showing partition alarm."""

    alarm_type_array = ["Police", "Fire", "Auxiliary"]

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        partition_id: str,
        unique_id: str,
        alarm_type: str,
    ) -> None:
        """Set up a binary sensor entity for partition alarm type."""
        super().__init__(QolsysPanel, partition_id, unique_id)
        self.QolsysPanel = QolsysPanel
        self._alarm_type = alarm_type
        self._attr_translation_key = f"partition_alarm_{alarm_type.lower()}"
        self._attr_unique_id = f"{self._partition_unique_id}_alarm_{alarm_type.lower()}"

    @property
    def is_on(self) -> bool:
        """Return if this partition alarm status."""
        partition_alarm = self._partition.alarm_type_array

        match self._alarm_type:
            case "Police":
                if (
                    PartitionAlarmType.POLICE_EMERGENCY in partition_alarm
                    or PartitionAlarmType.SILENT_POLICE_EMERGENCY in partition_alarm
                    or PartitionAlarmType.GLASS_BREAK_AWAY_ONLY in partition_alarm
                    or PartitionAlarmType.GLASS_BREAK in partition_alarm
                ):
                    return True

            case "Fire":
                if PartitionAlarmType.FIRE_EMERGENCY in partition_alarm:
                    return True

            case "Auxiliary":
                if (
                    PartitionAlarmType.AUXILIARY_EMERGENCY in partition_alarm
                    or PartitionAlarmType.SILENT_AUXILIARY_EMERGENCY in partition_alarm
                ):
                    return True

        return False


class PanelSensor(QolsysPanelSensorEntity, BinarySensorEntity):
    """A binary sensor entity for each panel sensor on Qolsys Panel."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        unique_id: str,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Set up a binary sensor entity for each panel sensor on Qolsys Panel."""
        super().__init__(QolsysPanel, entity_description.key, unique_id)
        self.entity_description = entity_description
        self._attr_unique_id = self._panelsensor_unique_id
        self._attr_translation_key = f"panel_{entity_description.key.lower()}"

    @property
    def is_on(self) -> bool:
        """Return if this fault has occurred."""

        match self.entity_description.key:
            case "AC_STATUS":
                return self.QolsysPanel.panel.AC_STATUS == "ON"

            case "PANEL_TAMPER_STATE":
                return self.QolsysPanel.panel.PANEL_TAMPER_STATE == "1"

            case "BATTERY_STATUS":
                return self.QolsysPanel.panel.BATTERY_STATUS != "OKAY"

            case "FAIL_TO_COMMUNICATE":
                return self.QolsysPanel.panel.FAIL_TO_COMMUNICATE != "true"

            case "GSM_CONNECTION_STATUS":
                return (
                    self.QolsysPanel.panel.GSM_CONNECTION_STATUS
                    != "gsm_error_no_signal"
                )

            case "ZWAVE_CONTROLLER":
                return self.QolsysPanel.panel.ZWAVE_CONTROLLER == "true"

            case "SECURE_ARMING":
                return self.QolsysPanel.panel.SECURE_ARMING == "true"

            case "AUTO_STAY":
                return self.QolsysPanel.panel.AUTO_STAY == "true"

            case "AUTO_ARM_STAY":
                return self.QolsysPanel.panel.AUTO_ARM_STAY == "true"

            case "CONTROL_4":
                return self.QolsysPanel.panel.CONTROL_4 == "true"

            case "AUTO_BYPASS":
                return self.QolsysPanel.panel.AUTO_BYPASS == "true"

            case _:
                return False  # Default case if no match found, should not happen with current descriptions


class ZoneSensor_Unreachable(QolsysZoneEntity, BinarySensorEntity):
    """A binary sensor entity for a zone unreachable."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, QolsysPanel: qolsys_controller, zone_id: int, unique_id: str
    ) -> None:
        """Set up a binary sensor entity for a zone unreachable."""
        super().__init__(QolsysPanel, zone_id, unique_id)
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_unique_id = f"{self._zone_unique_id}_unreachable"
        self._attr_translation_key = "zone_unreachable"

    @property
    def is_on(self) -> bool:
        """Return if this zone is unreachable."""
        return self._zone.sensorstatus != "Unreachable"


class ZoneSensor_Tamper(QolsysZoneEntity, BinarySensorEntity):
    """A binary sensor entity for a zone tamper."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, QolsysPanel: qolsys_controller, zone_id: int, unique_id: str
    ) -> None:
        """Set up a binary sensor entity for a zone tamper."""
        super().__init__(QolsysPanel, zone_id, unique_id)
        self._attr_device_class = BinarySensorDeviceClass.TAMPER
        self._attr_unique_id = f"{self._zone_unique_id}_tamper"
        self._attr_translation_key = "zone_tamper"

    @property
    def is_on(self) -> bool:
        """Return if this zone tamper is on."""
        return self._zone.sensorstatus == ZoneStatus.TAMPERED


class ZoneSensor_BatteryStatus(QolsysZoneEntity, BinarySensorEntity):
    """A binary sensor entity for a zone battery status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, QolsysPanel: qolsys_controller, zone_id: int, unique_id: str
    ) -> None:
        """Set up a binary sensor entity for a zone battery status."""
        super().__init__(QolsysPanel, zone_id, unique_id)
        self._attr_device_class = BinarySensorDeviceClass.BATTERY
        self._attr_unique_id = f"{self._zone_unique_id}_battery_status"
        self._attr_translation_key = "zone_battery_status"

    @property
    def is_on(self) -> bool:
        """Return if this zone battery status is low."""
        return self._zone.battery_status != "Normal"


class ZoneSensor_ACStatus(QolsysZoneEntity, BinarySensorEntity):
    """A binary sensor entity for a zone ac status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, QolsysPanel: qolsys_controller, zone_id: int, unique_id: str
    ) -> None:
        """Set up a binary sensor entity for a zone ac status."""
        super().__init__(QolsysPanel, zone_id, unique_id)
        self._attr_device_class = BinarySensorDeviceClass.PLUG
        self._attr_unique_id = f"{self._zone_unique_id}_ac_status"
        self._attr_translation_key = "zone_ac_status"

    @property
    def is_on(self) -> bool:
        """Return if this zone ac status is not normal."""
        return self._zone.ac_status == "Normal"


class ZonesSensor(QolsysZoneEntity, BinarySensorEntity):
    """A binary sensor entity for a zone in a Qolsys Panel."""

    _attr_name = None

    def __init__(
        self, QolsysPanel: qolsys_controller, zone_id: int, unique_id: str
    ) -> None:
        """Set up a binary sensor entity for a zone in a Qolsys Panel."""
        super().__init__(QolsysPanel, zone_id, unique_id)
        self._attr_unique_id = self._zone_unique_id

    @property
    def is_on(self) -> bool:
        """Return if this zone is on."""
        if self._zone.sensorstatus in {
            ZoneStatus.OPEN,
            ZoneStatus.ALARMED,
            ZoneStatus.ACTIVATED,
            ZoneStatus.DISCONNECTED,
            ZoneStatus.INACTIVE,
        }:
            return True

        return False

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the device class of this point sensor."""
        if self._zone.sensortype == ZoneSensorType.PANEL_MOTION:
            return BinarySensorDeviceClass.MOTION

        if self._zone.sensortype == ZoneSensorType.MOTION:
            return BinarySensorDeviceClass.MOTION

        if self._zone.sensortype == ZoneSensorType.DOOR_WINDOW:
            return BinarySensorDeviceClass.DOOR

        if self._zone.sensortype == ZoneSensorType.PANEL_GLASS_BREAK:
            return BinarySensorDeviceClass.PROBLEM

        if self._zone.sensortype == ZoneSensorType.GLASS_BREAK:
            return BinarySensorDeviceClass.PROBLEM

        if self._zone.sensortype == ZoneSensorType.SMOKE_DETECTOR:
            return BinarySensorDeviceClass.SMOKE

        if self._zone.sensortype == ZoneSensorType.SMOKE_M:
            return BinarySensorDeviceClass.SMOKE

        if self._zone.sensortype == ZoneSensorType.CO_DETECTOR:
            return BinarySensorDeviceClass.CO

        if self._zone.sensortype == ZoneSensorType.AUXILIARY_PENDANT:
            return BinarySensorDeviceClass.SAFETY

        if self._zone.sensortype == ZoneSensorType.WATER:
            return BinarySensorDeviceClass.MOISTURE

        if self._zone.sensortype == ZoneSensorType.BLUETOOTH:
            return None

        if self._zone.sensortype == ZoneSensorType.KEYPAD:
            return BinarySensorDeviceClass.PROBLEM

        if self._zone.sensortype == ZoneSensorType.KEY_FOB:
            return BinarySensorDeviceClass.SAFETY

        if self._zone.sensortype == ZoneSensorType.TILT:
            return BinarySensorDeviceClass.PROBLEM

        if self._zone.sensortype == ZoneSensorType.FREEZE:
            return BinarySensorDeviceClass.COLD

        if self._zone.sensortype == ZoneSensorType.HEAT:
            return BinarySensorDeviceClass.HEAT

        if self._zone.sensortype == ZoneSensorType.DOORBELL:
            return BinarySensorDeviceClass.PRESENCE

        return None


class ZwaveDevice_Status(QolsysZwaveEntity, BinarySensorEntity):
    """A binary sensor entity for a z-wave device status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: str, unique_id: str
    ) -> None:
        """Set up a binary sensor entity for a z-wave device status."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = f"{self._zwave_unique_id}_status"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_translation_key = "zwave_node_status"

    @property
    def is_on(self) -> bool:
        """Return this z-wave device status."""
        return self._node.node_status != "Normal"
