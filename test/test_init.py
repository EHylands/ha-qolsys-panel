"""Tests for the Qolsys Panel integration setup."""

from collections.abc import Generator
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from qolsys_controller.enum_qolsys import ControllerState, QolsysNotification
from qolsys_controller.errors import QolsysConfigError, QolsysMqttError, QolsysSslError

from custom_components.qolsys_panel import async_migrate_entry
from custom_components.qolsys_panel.const import (
    DOMAIN,
    OPTION_ARM_CODE,
    OPTION_DISARM_CODE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

LOST_MESSAGE = "Connection to Qolsys Panel lost, reconnecting"
RESTORED_MESSAGE = "Connection to Qolsys Panel restored"


@pytest.fixture(autouse=True)
def _zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Mock zeroconf: the integration manifest depends on it."""


@pytest.fixture
def mock_controller() -> Generator[MagicMock]:
    """Mock the qolsys_controller used by async_setup_entry."""
    controller = MagicMock()
    controller.run_forever = AsyncMock()
    controller.wait_until_connected = AsyncMock()
    controller.stop = AsyncMock()
    controller.controller_state = ControllerState.CONNECTED
    controller.panel.HARDWARE_VERSION = "IQ Panel 4"

    with (
        patch(
            "custom_components.qolsys_panel.qolsys_controller",
            return_value=controller,
        ),
        patch(
            "custom_components.qolsys_panel.get_local_ip",
            return_value="192.168.1.2",
        ),
        patch("custom_components.qolsys_panel.PLATFORMS", []),
    ):
        yield controller


def _get_status_callback(controller: MagicMock):
    """Return the PANEL_STATUS_UPDATE callback registered during setup."""
    callbacks = [
        call.args[1]
        for call in controller.state.register.call_args_list
        if call.args[0] is QolsysNotification.PANEL_STATUS_UPDATE
    ]
    assert len(callbacks) == 1
    return callbacks[0]


async def test_log_when_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
    caplog: pytest.LogCaptureFixture,
):
    """Test the connection loss is logged once and the recovery once."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    status_callback = _get_status_callback(mock_controller)
    caplog.set_level(logging.INFO)
    caplog.clear()

    # Connection lost: logged once, repeated reconnect attempts stay silent
    mock_controller.controller_state = ControllerState.RECONNECTING
    status_callback()
    status_callback()
    await hass.async_block_till_done()
    assert caplog.text.count(LOST_MESSAGE) == 1
    assert RESTORED_MESSAGE not in caplog.text

    # Connection restored: logged once
    mock_controller.controller_state = ControllerState.CONNECTED
    status_callback()
    status_callback()
    await hass.async_block_till_done()
    assert caplog.text.count(LOST_MESSAGE) == 1
    assert caplog.text.count(RESTORED_MESSAGE) == 1


async def test_no_log_on_shutdown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
    caplog: pytest.LogCaptureFixture,
):
    """Test an intentional shutdown is not logged as a lost connection."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    status_callback = _get_status_callback(mock_controller)
    caplog.set_level(logging.INFO)
    caplog.clear()

    mock_controller.controller_state = ControllerState.SHUTTING_DOWN
    status_callback()
    await hass.async_block_till_done()
    assert LOST_MESSAGE not in caplog.text


async def test_unload_unregisters_connection_logger(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
):
    """Test unloading the entry stops the controller and unregisters."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    status_callback = _get_status_callback(mock_controller)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_controller.stop.assert_awaited_once()
    mock_controller.state.unregister.assert_any_call(
        QolsysNotification.PANEL_STATUS_UPDATE, status_callback
    )


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        (TimeoutError(), ConfigEntryState.SETUP_RETRY),
        (QolsysConfigError("boom"), ConfigEntryState.SETUP_RETRY),
        (QolsysSslError("boom"), ConfigEntryState.SETUP_ERROR),
        (QolsysMqttError("boom"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_connection_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: MagicMock,
    error: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """A failed connection during setup leaves the entry retrying or errored."""
    mock_controller.wait_until_connected.side_effect = error
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_migrate_future_version_fails(hass: HomeAssistant) -> None:
    """A downgrade from a future version is refused."""
    entry = MockConfigEntry(domain=DOMAIN, version=2, minor_version=0)
    entry.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry) is False


async def test_migrate_current_version_noop(hass: HomeAssistant) -> None:
    """A current-version entry migrates successfully with no changes."""
    entry = MockConfigEntry(domain=DOMAIN, version=1, minor_version=0)
    entry.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry) is True


async def test_migrate_from_v0_adds_disarm_option(hass: HomeAssistant) -> None:
    """Migrating from v0 carries the arm-code option into the new disarm option."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=0,
        minor_version=0,
        options={OPTION_ARM_CODE: True},
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True
    assert entry.options[OPTION_DISARM_CODE] is True
    assert entry.version == 1
