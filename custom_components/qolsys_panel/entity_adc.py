"""Support for Qolsys Panel ADC Entity."""

from __future__ import annotations

from qolsys_controller import qolsys_controller

from homeassistant.helpers.device_registry import DeviceInfo

from .entity import QolsysPanelEntity

from .const import DOMAIN


class QolsysAdcEntity(QolsysPanelEntity):
    """Qolsys ADC Entity."""

    def __init__(
        self,
        QolsysPanel: qolsys_controller,
        device_id: str,
        unique_id: str,
    ) -> None:
        """Set up Qolsys ADC Entity."""
        super().__init__(QolsysPanel, unique_id)
        self._device_id = device_id
        self._service_id = 0
        self._adc_unique_id = f"{unique_id}_adc{device_id}"
        self._device = QolsysPanel.state.adc_device(self._device_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._adc_unique_id)},
            name=f"Virtual ADC{self._device_id} - {self._device.name}",
            model="Virtual ADC Device",
            manufacturer="Johnson Controls",
            via_device=(DOMAIN, unique_id),
        )

    async def async_added_to_hass(self) -> None:
        """Observe changes."""
        await super().async_added_to_hass()
        self._device.register(self.schedule_update_ha_stat)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing changes."""
        await super().async_will_remove_from_hass()
        self._device.unregister(self.schedule_update_ha_state)
