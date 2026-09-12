from __future__ import annotations

import logging
from abc import ABC
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Type, TypeVar

from ..automation.protocol_service import ServiceProtocol
from ..automation.service import AutomationService
from ..automation.service_battery import BatteryService
from ..automation.service_cover import CoverService
from ..automation.service_light import LightService
from ..automation.service_lock import LockService
from ..automation.service_meter import MeterService
from ..automation.service_outlet import OutletService
from ..automation.service_sensor import SensorService
from ..automation.service_siren import SirenService
from ..automation.service_status import StatusService
from ..automation.service_thermostat import ThermostatService
from ..automation.service_valve import ValveService
from ..automation_adc.service_cover import CoverServiceADC
from ..automation_adc.service_light import LightServiceADC
from ..automation_adc.service_status import StatusServiceADC
from ..automation_powerg.service_battery import BatteryServicePowerG
from ..automation_powerg.service_light import LightServicePowerG
from ..automation_powerg.service_lock import LockServicePowerG
from ..automation_powerg.service_status import StatusServicePowerG
from ..automation_zigbee.service_battery import BatteryServiceZigbee
from ..automation_zigbee.service_light import LightServiceZigbee
from ..automation_zigbee.service_lock import LockServiceZigbee
from ..automation_zigbee.service_status import StatusServiceZigbee
from ..automation_zwave.service_battery import BatteryServiceZwave
from ..automation_zwave.service_cover import CoverServiceZwave
from ..automation_zwave.service_light import LightServiceZwave
from ..automation_zwave.service_lock import LockServiceZwave
from ..automation_zwave.service_outlet import OutletServiceZwave
from ..automation_zwave.service_sensor import SensorServiceZwave
from ..automation_zwave.service_siren import SirenServiceZwave
from ..automation_zwave.service_status import StatusServiceZwave
from ..automation_zwave.service_thermostat import ThermostatServiceZwave
from ..automation_zwave.service_valve import ValveServiceZwave
from ..enum_qolsys import AutomationDeviceProtocol, QolsysNotification
from ..observable import Event, QolsysObservable

if TYPE_CHECKING:
    from ..controller import QolsysController

LOGGER = logging.getLogger(__name__)


class QolsysAutomationDevice(QolsysObservable, ABC):
    def __init__(self, controller: QolsysController, dev_dict: dict[str, str]) -> None:
        super().__init__()

        self._controller: QolsysController = controller
        self._services: dict[int, list[AutomationService]] = {}

        # Main device identifier
        self._virtual_node_id: str = dev_dict.get("virtual_node_id", "")

        self._id: str = dev_dict.get("_id", "")
        self._partition_id: str = dev_dict.get("partition_id", "")
        self._device_id: str = dev_dict.get("device_id", "")
        self._device_name: str = dev_dict.get("device_name", "")
        self._device_type: str = dev_dict.get("device_type", "")
        self._extras: str = dev_dict.get("extras", "")
        self._protocol: str = dev_dict.get("protocol", "")
        self._state: str = dev_dict.get("state", "")
        self._status: str = dev_dict.get("status", "")
        self._version: str = dev_dict.get("version", "")
        self._end_point: str = dev_dict.get("end_point", "")
        self._is_autolocking_enabled: str = dev_dict.get("is_autolocking_enabled", "")
        self._endpoint_secure_cmd_classes: str = dev_dict.get("endpoint_secure_cmd_classes", "")
        self._automation_id: str = dev_dict.get("automation_id", "")
        self._node_battery_level_value: str = dev_dict.get("node_battery_level_value", "")
        self._last_updated_date: str = dev_dict.get("last_updated_date", "")
        self._manufacturer_id: str = dev_dict.get("manufacturer_id", "")
        self._endpoint_cmd_classes: str = dev_dict.get("endpoint_cmd_classes", "")
        self._nodeid_cmd_classes: str = dev_dict.get("nodeid_cmd_classes", "")
        self._is_device_hidden: str = dev_dict.get("is_device_hidden", "")
        self._nodeid_secure_cmd_classes: str = dev_dict.get("nodeid_secure_cmd_classes", "")
        self._created_date: str = dev_dict.get("created_date", "")
        self._smart_energy_optimizer: str = dev_dict.get("smart_energy_optimizer", "")
        self._linked_security_zone: str = dev_dict.get("linked_security_zone", "")

        self._available_services: list[type[Any]] = [
            BatteryService,
            CoverService,
            LightService,
            LockService,
            MeterService,
            OutletService,
            SensorService,
            SirenService,
            StatusService,
            ThermostatService,
            ValveService,
        ]

        match self.device_type:
            case "Light":
                self.service_add_light_service(int(self._end_point))

            case "Door Lock":
                self.service_add_lock_service(int(self._end_point))

            case "Garage Door":
                self.service_add_cover_service(int(self._end_point))

            case "External Siren":
                self.service_add_siren_service(int(self._end_point))

            case "Water Valve":
                self.service_add_valve_service(int(self._end_point))

            case "Thermostat":
                self.service_add_thermostat_service(int(self._end_point))

            case "Thermometer":  # Device will auto discover multilevel sensors
                pass

            case "Energy Clamp":  # Device will auto discover meters
                pass

            case "Repeater":  # No services
                pass

            case "Smart Socket":
                self.service_add_outlet_service(int(self._end_point))

    def info(self) -> None:
        pass

    T = TypeVar("T", bound=AutomationService)

    def service_get(self, service_type: Type[T], endpoint: int = 0) -> T | None:
        services_list = self._services.get(endpoint, [])
        for service in services_list:
            if isinstance(service, service_type):
                return service
        return None

    def service_get_protocol(self, service_type: type[AutomationService]) -> list[AutomationService]:
        services: list[AutomationService] = []

        for endpoint, services_list in self._services.items():
            for service in services_list:
                if isinstance(service, service_type):
                    services.append(service)

        return services

    def service_add(self, service: AutomationService) -> None:
        if not isinstance(service, ServiceProtocol):
            LOGGER.error(
                "%s[%s] - Unable to add Service (not a ServiceProtocol): %s",
                self.prefix,
                service.endpoint,
                type(service),
            )
            return

        for service_type in self._available_services:
            if isinstance(service, service_type):
                if self.service_get(service_type, service.endpoint) is not None:
                    LOGGER.error(
                        "%s[%s] - Unable to add Service (already exists): %s",
                        self.prefix,
                        service.endpoint,
                        type(service),
                    )
                    return
                self._services.setdefault(service.endpoint, []).append(service)
                return

        LOGGER.error(
            "%s - Unable to add Service (unknown type): %s",
            self.prefix,
            type(service),
        )

    def service_add_valve_service(self, endpoint: int = 0) -> None:
        valve_service: AutomationService | None = None

        match self.protocol:
            case AutomationDeviceProtocol.ADC:
                pass

            case AutomationDeviceProtocol.POWERG:
                pass

            case AutomationDeviceProtocol.ZWAVE:
                valve_service = ValveServiceZwave(automation_device=self, endpoint=endpoint)

        if valve_service is not None:
            self.service_add(valve_service)
            return

    def service_add_siren_service(self, endpoint: int = 0) -> None:
        siren_service: AutomationService | None = None

        match self.protocol:
            case AutomationDeviceProtocol.ADC:
                pass

            case AutomationDeviceProtocol.POWERG:
                pass

            case AutomationDeviceProtocol.ZWAVE:
                siren_service = SirenServiceZwave(automation_device=self, endpoint=endpoint)

        if siren_service is not None:
            self.service_add(siren_service)
            return

    def service_add_outlet_service(self, endpoint: int = 0) -> None:
        outlet_service: AutomationService | None = None

        match self.protocol:
            case AutomationDeviceProtocol.ADC:
                pass

            case AutomationDeviceProtocol.POWERG:
                pass

            case AutomationDeviceProtocol.ZWAVE:
                outlet_service = OutletServiceZwave(automation_device=self, endpoint=endpoint)

        if outlet_service is not None:
            self.service_add(outlet_service)
            return

    def service_add_thermostat_service(self, endpoint: int = 0) -> None:
        thermostat_service: AutomationService | None = None

        match self.protocol:
            case AutomationDeviceProtocol.ADC:
                pass

            case AutomationDeviceProtocol.POWERG:
                pass

            case AutomationDeviceProtocol.ZWAVE:
                thermostat_service = ThermostatServiceZwave(automation_device=self, endpoint=endpoint)

        if thermostat_service is not None:
            self.service_add(thermostat_service)
            return

    def service_add_sensor_service(self, endpoint: int = 0) -> None:
        sensor_service: AutomationService | None = None

        match self.protocol:
            case AutomationDeviceProtocol.ADC:
                pass

            case AutomationDeviceProtocol.POWERG:
                pass

            case AutomationDeviceProtocol.ZWAVE:
                sensor_service = SensorServiceZwave(automation_device=self, endpoint=endpoint)

        if sensor_service is not None:
            self.service_add(sensor_service)
            return

    def service_add_light_service(self, endpoint: int = 0) -> None:
        light_service: AutomationService | None = None

        match self.protocol:
            case AutomationDeviceProtocol.ADC:
                light_service = LightServiceADC(automation_device=self, endpoint=endpoint)

            case AutomationDeviceProtocol.POWERG:
                light_service = LightServicePowerG(automation_device=self, endpoint=endpoint)

            case AutomationDeviceProtocol.ZWAVE:
                light_service = LightServiceZwave(automation_device=self, endpoint=endpoint)

            case AutomationDeviceProtocol.ZIGBEE:
                light_service = LightServiceZigbee(automation_device=self, endpoint=endpoint)

        if light_service is not None:
            self.service_add(light_service)
            return

    def service_add_lock_service(self, endpoint: int = 0) -> None:
        lock_service: AutomationService | None = None

        match self.protocol:
            case AutomationDeviceProtocol.POWERG:
                lock_service = LockServicePowerG(self, endpoint=endpoint)

            case AutomationDeviceProtocol.ZWAVE:
                lock_service = LockServiceZwave(self, endpoint=endpoint)

            case AutomationDeviceProtocol.ZIGBEE:
                lock_service = LockServiceZigbee(self, endpoint=endpoint)

        if lock_service is not None:
            self.service_add(lock_service)
            return

        LOGGER.error("%s - Unable to add Lock Service to endpoint%s", self.prefix, endpoint)

    def service_add_battery_service(self, endpoint: int = 0) -> None:
        battery_service: AutomationService | None = None

        match self.protocol:
            case AutomationDeviceProtocol.POWERG:
                battery_service = BatteryServicePowerG(automation_device=self, endpoint=endpoint)

            case AutomationDeviceProtocol.ZWAVE:
                battery_service = BatteryServiceZwave(automation_device=self, endpoint=endpoint)

            case AutomationDeviceProtocol.ZIGBEE:
                battery_service = BatteryServiceZigbee(automation_device=self, endpoint=endpoint)

            case AutomationDeviceProtocol.ADC:
                pass

        if battery_service is not None:
            self.service_add(battery_service)
            return

        LOGGER.error("%s - Unable to add Battery Service to endpoint%s", self.prefix, endpoint)

    def service_add_status_service(self, endpoint: int = 0) -> None:
        service: StatusService | None = None

        match self.protocol:
            case AutomationDeviceProtocol.ADC:
                service = StatusServiceADC(automation_device=self, endpoint=endpoint)

            case AutomationDeviceProtocol.POWERG:
                service = StatusServicePowerG(automation_device=self, endpoint=endpoint)

            case AutomationDeviceProtocol.ZWAVE:
                service = StatusServiceZwave(automation_device=self, endpoint=endpoint)

            case AutomationDeviceProtocol.ZIGBEE:
                service = StatusServiceZigbee(automation_device=self, endpoint=endpoint)

        if service is not None:
            self.service_add(service)
            return

    def service_add_cover_service(self, endpoint: int = 0) -> None:
        cover_service: AutomationService | None = None

        match self.protocol:
            case AutomationDeviceProtocol.ADC:
                cover_service = CoverServiceADC(automation_device=self, endpoint=endpoint)

            case AutomationDeviceProtocol.POWERG:
                pass

            case AutomationDeviceProtocol.ZWAVE:
                cover_service = CoverServiceZwave(automation_device=self, endpoint=endpoint)

        if cover_service is not None:
            self.service_add(cover_service)
            return

    def update_automation_services(self) -> None:
        for endpoint, services_list in self._services.items():
            for service in services_list:
                service.update_automation_service()

    def update_automation_device(self, data: dict[str, str]) -> None:
        # Check if we are updating same virtual_node_id
        virtual_node_id_update = data.get("virtual_node_id", "")
        if virtual_node_id_update != self._virtual_node_id:
            LOGGER.error(
                "Updating AutDev%s (%s) with %s (different virtual_node_id)",
                self._virtual_node_id,
                self._device_name,
                virtual_node_id_update,
            )
            return

        self.start_batch_update()

        if "device_name" in data:
            self._device_name = data.get("device_name", "")

        if "partition_id" in data:
            self._partition_id = data.get("partition_id", "")

        if "state" in data:
            self._state = data.get("state", "")

        if "status" in data:
            self._status = data.get("status", "")

        if "node_battery_level_value" in data:
            self._node_battery_level_value = data.get("node_battery_level_value", "")

        if "extras" in data:
            self.extras = data.get("extras", "")

        self.update_automation_services()

        self.end_batch_update()

    # -----------------------------
    # properties + setters
    # -----------------------------

    @property
    def controller(self) -> QolsysController:
        return self._controller

    @property
    def services(self) -> dict[int, list[AutomationService]]:
        return self._services

    @property
    def prefix(self, endpoint: int | None = None) -> str:
        return f"[AutDev][{self.protocol.name}][{self.virtual_node_id}]({self.device_name})"

    @property
    def device_id(self) -> str:
        return self._device_id

    @device_id.setter
    def device_id(self, value: str) -> None:
        if self._device_id != value:
            LOGGER.debug("%s - device_id: %s", self.prefix, value)
            self._device_id = value
            self.notify(Event(QolsysNotification.AUTOMATION_UPDATE, self, self.to_dict_event()))

    @property
    def virtual_node_id(self) -> str:
        return self._virtual_node_id

    @virtual_node_id.setter
    def virtual_node_id(self, value: str) -> None:
        if self._virtual_node_id != value:
            LOGGER.debug("%s - virtual_node_id: %s", self.prefix, value)
            self._virtual_node_id = value
            self.notify(Event(QolsysNotification.AUTOMATION_UPDATE, self, self.to_dict_event()))

    @property
    def partition_id(self) -> str:
        return self._partition_id

    @partition_id.setter
    def partition_id(self, value: str) -> None:
        if self._partition_id != value:
            LOGGER.debug("AutDev%s (%s) - partition_id: %s", self.device_id, self.device_name, value)
            self._partition_id = value
            self.notify(Event(QolsysNotification.AUTOMATION_UPDATE, self, self.to_dict_event()))

    @property
    def state(self) -> str:
        return self._state

    @state.setter
    def state(self, value: str) -> None:
        if self._state != value:
            # LOGGER.debug("AutDev%s (%s) - state: %s", self.device_id, self.device_name, value)
            self._state = value
            self.notify(Event(QolsysNotification.AUTOMATION_UPDATE, self, self.to_dict_event()))

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        if self._status != value:
            # LOGGER.debug("AutDev%s (%s) - status: %s", self.device_id, self.device_name, value)
            self._status = value
            self.notify(Event(QolsysNotification.AUTOMATION_UPDATE, self, self.to_dict_event()))

    @property
    def device_name(self) -> str:
        return self._device_name

    @device_name.setter
    def device_name(self, value: str) -> None:
        if self._device_name != value:
            LOGGER.debug("%s - device_name: %s", self.prefix, value)
            self._device_name = value
            self.notify(Event(QolsysNotification.AUTOMATION_UPDATE, self, self.to_dict_event()))

    @property
    def device_type(self) -> str:
        return self._device_type

    @device_type.setter
    def device_type(self, value: str) -> None:
        if self._device_type != value:
            LOGGER.debug("AutDev%s (%s) - device_type: %s", self.device_id, self.device_name, value)
            self._device_type = value
            self.notify(Event(QolsysNotification.AUTOMATION_UPDATE, self, self.to_dict_event()))

    @property
    def extras(self) -> str:
        return self._extras

    @extras.setter
    def extras(self, value: str) -> None:
        if self._extras != value:
            # LOGGER.debug("AutDev%s (%s) - extras: %s", self.device_id, self.device_name, value)
            self._extras = value
            self.notify(Event(QolsysNotification.AUTOMATION_UPDATE, self, self.to_dict_event()))

    @property
    def protocol(self) -> AutomationDeviceProtocol:
        try:
            return AutomationDeviceProtocol(self._protocol)
        except ValueError:
            return AutomationDeviceProtocol.UNKNOWN

    @protocol.setter
    def protocol(self, value: str) -> None:
        if self._protocol != value:
            LOGGER.debug("AutDev%s (%s) - protocol: %s", self.device_id, self.device_name, value)
            self._protocol = value
            self.notify(Event(QolsysNotification.AUTOMATION_UPDATE, self, self.to_dict_event()))

    def to_dict(self) -> dict[str, str]:
        return {
            "_id": self._id,
            "virtual_node_id": self._virtual_node_id,
            "partition_id": self._partition_id,
            "device_id": self._device_id,
            "device_name": self._device_name,
            "device_type": self._device_type,
            "protocol": self._protocol,
            "state": self._state,
            "status": self._status,
            "version": self._version,
            "end_point": self._end_point,
            "is_autolocking_enabled": self._is_autolocking_enabled,
            "endpoint_secure_cmd_classes": self._endpoint_secure_cmd_classes,
            "automation_id": self._automation_id,
            "node_battery_level_value": self._node_battery_level_value,
            "last_updated_date": self._last_updated_date,
            "manufacturer_id": self._manufacturer_id,
            "endpoint_cmd_classes": self._endpoint_cmd_classes,
            "nodeid_cmd_classes": self._nodeid_cmd_classes,
            "is_device_hidden": self._is_device_hidden,
            "nodeid_secure_cmd_classes": self._nodeid_secure_cmd_classes,
            "created_date": self._created_date,
            "smart_energy_optimizer": self._smart_energy_optimizer,
            "linked_security_zone": self._linked_security_zone,
        }

    def to_dict_event(self) -> dict[str, Any]:
        services_array: list[dict[str, Any]] = []
        services_dict: dict[int, list[dict[str, Any]]] = {}
        for endpoint, services_list in self._services.items():
            for service in services_list:
                services_dict.setdefault(endpoint, []).append(service.to_dict_event())
                services_array.append(service.to_dict_event())

        return {
            "id": int(self._virtual_node_id),
            "type": "automation_device",
            "state": {
                "services": services_array,
            },
            "attributes": {
                "protocol": self.protocol.name.lower(),
                "name": self._device_name,
                "device_type": self._device_type.lower().replace(" ", "_"),
            },
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "version": 1,
        }
