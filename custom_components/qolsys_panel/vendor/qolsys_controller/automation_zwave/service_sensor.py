from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..automation.service_sensor import QolsysSensor, SensorService
from ..automation.service_thermostat import ThermostatService
from ..automation_zwave.service_thermostat import ThermostatServiceZwave
from ..enum_qolsys import QolsysSensorScale

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice


LOGGER = logging.getLogger(__name__)


class SensorServiceZwave(SensorService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)

    def update_zwave_service(self, data: dict[str, Any]) -> None:
        # Update Sensors Values
        for key, value in data.items():
            if key == "AIR TEMPERATURE":
                temperature: float | None = value.get("Fahrenheit (F)", None)
                sensor = self.sensor(QolsysSensorScale.TEMPERATURE_FAHRENHEIT)
                if not sensor:
                    sensor = QolsysSensor(self._automation_device, self, QolsysSensorScale.TEMPERATURE_FAHRENHEIT)
                    self.sensor_add(sensor)
                sensor.value = temperature

            if key == "HUMIDITY":
                humidity: float | None = value.get("Percentage value (%)", None)
                sensor = self.sensor(QolsysSensorScale.RELATIVE_HUMIDITY)
                if not sensor:
                    sensor = QolsysSensor(self._automation_device, self, QolsysSensorScale.RELATIVE_HUMIDITY)
                    self.sensor_add(sensor)
                sensor.value = humidity

                # Check if thermostat service exists on same endpoint and update current humidity
                thermostat_service = self.automation_device.service_get(ThermostatServiceZwave, self.endpoint)
                if thermostat_service:
                    if isinstance(thermostat_service, ThermostatService):
                        thermostat_service.current_humidity = humidity

    def update_automation_service(self) -> None:
        pass
