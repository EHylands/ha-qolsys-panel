from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from ..automation.service_meter import MeterService
from ..enum_qolsys import QolsysMeterRateType, QolsysMeterScale, QolsysMeterType, map_to_zwave_meter_scale
from ..enum_zwave import ZwaveCommandClass
from ..mqtt_command import MQTTCommand_ZWave

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice


LOGGER = logging.getLogger(__name__)


class MeterServiceZwave(MeterService):
    def __init__(self, automation_device: QolsysAutomationDevice, endpoint: int = 0) -> None:
        super().__init__(automation_device=automation_device, endpoint=endpoint)

    def update_zwave_service(self, data: dict[str, Any], update_meter_value: bool = True) -> None:
        # Update Meter Type
        type: str | int = data.get("meter_type", "")
        if type == "ENERGY_METER" or type == QolsysMeterType.ELECTRIC_METER:
            self.meter_type = QolsysMeterType.ELECTRIC_METER

        # Upate Rate Type
        if "meter_ratetype_supported" in data:
            rate_type: int = data.get("meter_ratetype_supported", -1)
            try:
                self.rate_type = QolsysMeterRateType(rate_type)
            except (ValueError, TypeError):
                LOGGER.error("%s - MeterService ZWave - Unknown MeterRateType, Setting to UNSPECIFIED", self.prefix)
                self.rate_type = QolsysMeterRateType.UNSPECIFIED

        # Update Master Reset Flag
        if "meter_master_reset_flag" in data:
            self.master_reset_flag = bool(data.get("meter_master_reset_flag", False))

        # Update Supported Scales
        if "meter_scale_supported" in data:
            try:
                supported_scales: list[QolsysMeterScale] = []
                scale_values: list[str] = json.loads(data.get("meter_scale_supported", "[]"))
                scales = [s.strip() for s in scale_values]

                for scale in scales:
                    for qolsys_scale in QolsysMeterScale:
                        if scale.lower() == qolsys_scale.name.lower():
                            supported_scales.append(qolsys_scale)

                self.supported_scales = supported_scales

            except json.JSONDecodeError:
                LOGGER.error(
                    "%s - Error parsing meter_scale_supported: %s", self.prefix, data.get("meter_scale_supported", "[]")
                )
                self.supported_scales = []

        # Update Meter Values

        if not update_meter_value:
            return

        if "meter_scale_reading_values" in data:
            meter_scale_values: dict[str, Any] = data.get("meter_scale_reading_values", {})
            for key, value in meter_scale_values.items():
                # Try to match the scale to a known QolsysMeterScale, if it doesn't match skip it
                for scale in QolsysMeterScale:
                    if key.strip().lower() == scale.name.lower():
                        if scale in self.supported_scales:
                            sensor = self.meter(scale)
                            if sensor is not None:
                                sensor.value = float(value)

    def update_automation_service(self) -> None:
        pass

    async def refresh_meter_zwave(self) -> None:
        zwave_command = MQTTCommand_ZWave(
            self.automation_device.controller,
            self.automation_device.virtual_node_id,
            str(self.endpoint),
            [ZwaveCommandClass.Meter.value, 0x01],
        )
        await zwave_command.send_command()

        for meter in self.meters:
            zwave_command = MQTTCommand_ZWave(
                self.automation_device.controller,
                self.automation_device.virtual_node_id,
                str(self.endpoint),
                [ZwaveCommandClass.Meter.value, 0x01, int(map_to_zwave_meter_scale(self.meter_type, meter.unit)) & 0x07],
            )
            await zwave_command.send_command()

            zwave_command = MQTTCommand_ZWave(
                self.automation_device.controller,
                self.automation_device.virtual_node_id,
                "0",
                [
                    0x60,
                    0x0D,
                    0x00,
                    self.endpoint,
                    ZwaveCommandClass.Meter.value,
                    0x01,
                    map_to_zwave_meter_scale(self.meter_type, meter.unit) & 0x07,
                ],
            )
            await zwave_command.send_command()
