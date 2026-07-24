"""Tests for the Qolsys Panel diagnostics."""

from unittest.mock import MagicMock

from conftest import PANEL_MAC

from custom_components.qolsys_panel.const import CONF_IMEI, CONF_RANDOM_MAC
from custom_components.qolsys_panel.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant

ENTRY_DATA = {
    CONF_HOST: "192.168.1.50",
    CONF_MAC: PANEL_MAC,
    CONF_IMEI: "123456789012345",
    CONF_RANDOM_MAC: "aa:bb:cc:dd:ee:01",
}


def _entry(runtime_data) -> MagicMock:
    entry = MagicMock()
    entry.data = dict(ENTRY_DATA)
    entry.runtime_data = runtime_data
    return entry


async def test_diagnostics_without_runtime_data(hass: HomeAssistant) -> None:
    """With no runtime data, only redacted entry data is returned."""
    result = await async_get_config_entry_diagnostics(hass, _entry(None))

    assert set(result) == {"entry_data"}
    assert result["entry_data"][CONF_HOST] == REDACTED
    assert result["entry_data"][CONF_MAC] == REDACTED


async def test_diagnostics_with_runtime_data(hass: HomeAssistant) -> None:
    """With runtime data, panel/partition/zone data is included and redacted."""
    panel = MagicMock()

    partition = MagicMock()
    partition.id = "1"
    partition.name = "Main"
    panel.state.partitions = [partition]

    zone = MagicMock()
    zone.to_dict.return_value = {"id": 1, "sensorname": "Front Door"}
    panel.state.zones = [zone]

    device = MagicMock()
    device.to_dict.return_value = {"name": "Lock"}
    panel.state.automation_devices = [device]

    adc = MagicMock()
    adc.to_dict.return_value = {"id": "adc1"}
    panel.panel.db.get_adc_devices.return_value = [adc]

    result = await async_get_config_entry_diagnostics(hass, _entry(panel))

    assert set(result) == {"entry_data", "data"}
    assert result["entry_data"][CONF_IMEI] == REDACTED
    # Partition name and zone sensorname are redacted in the payload.
    assert result["data"]["partitions"][0]["name"] == REDACTED
    assert result["data"]["zones"][0]["sensorname"] == REDACTED
    assert result["data"]["zones"][0]["id"] == 1
