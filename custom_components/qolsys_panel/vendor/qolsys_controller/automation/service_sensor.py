from __future__ import annotations

__all__ = ["SensorService"]

import logging
from typing import TYPE_CHECKING, Any

from ..automation.service import AutomationService
from ..enum_qolsys import QolsysNotification, QolsysSensorScale
from ..observable import Event

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice

LOGGER = logging.getLogger(__name__)


class QolsysSensor:
    def __init__(
        self,
        parent_device: QolsysAutomationDevice,
        parent_service: SensorService,
        unit: QolsysSensorScale,
    ) -> None:
        self._parent_device: QolsysAutomationDevice = parent_device
        self._parent_service: SensorService = parent_service
        self._value: float | None = None
        self._unit: QolsysSensorScale = unit

    @property
    def unit(self) -> QolsysSensorScale:
        return self._unit

    @property
    def value(self) -> float | None:
        return self._value

    @value.setter
    def value(self, new_value: float | None) -> None:
        if self._value != new_value:
            self._value = new_value
            LOGGER.debug("%s - value: %s (%s)", self._parent_service.prefix, new_value, self._unit.name)
            self._parent_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self._parent_device, self._parent_device.to_dict_event())
            )


class SensorService(AutomationService):
    def __init__(self, automation_device: "QolsysAutomationDevice", endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)
        self._service_name = "SensorService"
        self._sensors: list[QolsysSensor] = []

    @property
    def sensors(self) -> list[QolsysSensor]:
        return self._sensors

    def sensor(self, unit: QolsysSensorScale) -> QolsysSensor | None:
        for sensor in self._sensors:
            if sensor.unit == unit:
                return sensor
        return None

    def sensor_add(self, new_sensor: QolsysSensor) -> None:
        for sensor in self._sensors:
            if sensor._unit == new_sensor._unit:
                LOGGER.error("Error Adding Sensor, unit already present")
                return
        self._sensors.append(new_sensor)
        self._automation_device.notify(
            Event(QolsysNotification.AUTOMATION_UPDATE, self._automation_device, self._automation_device.to_dict_event())
        )

        # Notify state
        self.automation_device._controller.state.notify(
            Event(
                QolsysNotification.AUTOMATION_SENSOR_ADD,
                self._automation_device,
                {
                    "virtual_node_id": self.automation_device.virtual_node_id,
                    "endpoint": self.endpoint,
                    "unit": new_sensor.unit,
                },
            )
        )

    def update_automation_service(self) -> None:
        pass

    def info(self) -> list[str]:
        str = []
        for sensor in self.sensors:
            str.append(f"{self.prefix} - sensor: {sensor.value} ({sensor.unit.name})")
        return str

    def to_dict_event(self) -> dict[str, Any]:
        return {
            "service_type": self.service_name,
            "state": {
                "sensors": [{"value": sensor.value, "unit": sensor.unit.name} for sensor in self.sensors],
            },
            "attributes": {
                "endpoint": self.endpoint,
            },
            "capabilities": {},
        }
