"""Support for Qolsys Z-Wave Thermostats."""

from __future__ import annotations

from qolsys_controller import qolsys_controller

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import QolsysZwaveThermostatEntity
from .types import QolsysPanelConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Thermostats entities."""
    QolsysPanel = config_entry.runtime_data

    entities: list[QolsysZwaveThermostatEntity] = []

    for thermostat in QolsysPanel.state.zwave_thermostats:
        entities.append(
            ZWaveThermostat(QolsysPanel, thermostat.node_id, config_entry.unique_id)
        )

    async_add_entities(entities)


class ZWaveThermostat(QolsysZwaveThermostatEntity, ClimateEntity):
    """An Z-Wave Thermostat entity for a qolsys panel."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self, QolsysPanel: qolsys_controller, node_id: int, unique_id: str
    ) -> None:
        """Initialise a Qolsys Z-Wave Thermostat entity."""
        super().__init__(QolsysPanel, node_id, unique_id)
        self._attr_unique_id = self._zwave_thermostat_unique_id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.QolsysPanel.plugin.connected and self._thermostat.node_status == 'Normal'

    @property
    def current_humidity(self):
        return None

    @property
    def current_temperature(self) -> float:
        return float(self._thermostat.thermostat_current_temp)

    @property
    def target_temperature(self) -> float:
        return float(self._thermostat.thermostat_target_temp)

    @property
    def temperature_unit(self) -> str:  # noqa: D102
        panel_temp_unit = self._thermostat.thermostat_device_temp_unit

        if panel_temp_unit == "F":
            return "TEMP_FAHRENHEIT"

        if panel_temp_unit == "C":
            return "TEMP_CELSIUS"

        return None

    @property
    def fan_mode(self):
        return None

    @property
    def fan_modes(self):
        return None

    @property
    def hvac_action(self):
        return None

    @property
    def hvac_mode(self):
        return None

    @property
    def hvac_modes(self):
        return []

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""

    async def async_turn_on(self):
        """Turn the entity on."""

    async def async_turn_off(self):
        """Turn the entity off."""

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
