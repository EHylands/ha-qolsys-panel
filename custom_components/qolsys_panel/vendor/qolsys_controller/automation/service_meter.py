from __future__ import annotations

__all__ = ["MeterService"]

import logging
from typing import TYPE_CHECKING, Any

from ..automation.service import AutomationService
from ..enum_qolsys import QolsysMeterRateType, QolsysMeterScale, QolsysMeterType, QolsysNotification
from ..observable import Event

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice

LOGGER = logging.getLogger(__name__)


class QolsysMeter:
    def __init__(
        self,
        parent_device: QolsysAutomationDevice,
        parent_service: MeterService,
        unit: QolsysMeterScale,
    ) -> None:
        self._parent_device: QolsysAutomationDevice = parent_device
        self._parent_service: MeterService = parent_service
        self._value: float | None = None
        self._unit: QolsysMeterScale = unit
        self._delta_time: int | None = None
        self._previous_value: float | None = None

    @property
    def unit(self) -> QolsysMeterScale:
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


class MeterService(AutomationService):
    def __init__(self, automation_device: "QolsysAutomationDevice", endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)
        self._service_name = "MeterService"
        self._meters: list[QolsysMeter] = []
        self._meter_type: QolsysMeterType = QolsysMeterType.UNKNOWN
        self._rate_type: QolsysMeterRateType = QolsysMeterRateType.UNSPECIFIED
        self._master_reset_flag: bool = False
        self._supported_scales: list[QolsysMeterScale] = []

    @property
    def meter_type(self) -> QolsysMeterType:
        return self._meter_type

    @meter_type.setter
    def meter_type(self, value: QolsysMeterType) -> None:
        if self._meter_type != value:
            self._meter_type = value
            LOGGER.debug("%s - meter_type: %s", self.prefix, value.name)
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )

    @property
    def supported_scales(self) -> list[QolsysMeterScale]:
        return self._supported_scales

    @supported_scales.setter
    def supported_scales(self, value: list[QolsysMeterScale]) -> None:
        if self._supported_scales != value:
            for scale in value:
                if scale not in self._supported_scales:
                    self._supported_scales.append(scale)
                    self.meter_add(QolsysMeter(parent_device=self._automation_device, parent_service=self, unit=scale))
                    self.automation_device.notify(
                        Event(
                            QolsysNotification.AUTOMATION_UPDATE,
                            self.automation_device,
                            self.automation_device.to_dict_event(),
                        )
                    )
            LOGGER.debug("%s - supported_scales: %s", self.prefix, [] if not value else ", ".join([s.name for s in value]))

    @property
    def master_reset_flag(self) -> bool:
        return self._master_reset_flag

    @master_reset_flag.setter
    def master_reset_flag(self, value: bool) -> None:
        if self._master_reset_flag != value:
            self._master_reset_flag = value
            LOGGER.debug("%s - master_reset_flag: %s", self.prefix, value)
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )

    @property
    def rate_type(self) -> QolsysMeterRateType:
        return self._rate_type

    @rate_type.setter
    def rate_type(self, value: QolsysMeterRateType) -> None:
        if self._rate_type != value:
            self._rate_type = value
            LOGGER.debug("%s - rate_type: %s", self.prefix, value.name)
            self.automation_device.notify(
                Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
            )

    @property
    def meters(self) -> list[QolsysMeter]:
        return self._meters

    def meter(self, unit: QolsysMeterScale) -> QolsysMeter | None:
        for meter in self._meters:
            if meter.unit == unit:
                return meter
        return None

    def meter_add(self, new_meter: QolsysMeter) -> None:
        meter = self.meter(new_meter.unit)
        if meter is not None:
            LOGGER.error("Error Adding meter, unit already present")
            return

        self._meters.append(new_meter)
        self._automation_device.notify(
            Event(QolsysNotification.AUTOMATION_UPDATE, self.automation_device, self.automation_device.to_dict_event())
        )

        self._automation_device._controller.state.notify(
            Event(
                QolsysNotification.AUTOMATION_METER_ADD,
                self._automation_device,
                {
                    "virtual_node_id": self._automation_device.virtual_node_id,
                    "endpoint": self.endpoint,
                    "unit": new_meter.unit,
                },
            )
        )

    def update_automation_service(self) -> None:
        pass

    def info(self) -> list[str]:
        str = []
        str.append(f"{self.prefix} - meter_type: {self.meter_type.name}")
        str.append(f"{self.prefix} - rate_type: {self.rate_type.name}")
        for meter in self.meters:
            str.append(f"{self.prefix} - Meter: {meter.value} ({meter.unit.name})")
        return str

    def to_dict_event(self) -> dict[str, Any]:
        return {
            "service_type": self.service_name,
            "state": {
                "meters": [{"value": meter.value, "unit": meter.unit.name} for meter in self.meters],
            },
            "attributes": {
                "endpoint": self.endpoint,
                "meter_type": self.meter_type.name,
                "rate_type": self.rate_type.name,
                "master_reset_flag": self.master_reset_flag,
            },
            "capabilities": {
                "supported_scales": [scale.name for scale in self.supported_scales],
            },
        }
