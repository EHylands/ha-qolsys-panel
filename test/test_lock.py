"""Tests for the Qolsys Panel locks."""

from unittest.mock import AsyncMock, MagicMock

from conftest import PANEL_MAC
import pytest

from custom_components.qolsys_panel.lock import AutomationDeviceLock, async_setup_entry
from homeassistant.components.lock import LockEntityFeature
from homeassistant.core import HomeAssistant

UID = PANEL_MAC


@pytest.fixture
def controller() -> MagicMock:
    """A controller mock with one automation device."""
    c = MagicMock()
    service = MagicMock()
    service.endpoint = 0
    device = MagicMock()
    device.virtual_node_id = "5"
    device.service_get_protocol.return_value = [service]
    c.state.automation_devices = [device]
    return c


async def test_async_setup_entry_creates_entities(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup builds a lock per automation-device lock service."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], AutomationDeviceLock)


def test_supports_open_feature(controller: MagicMock) -> None:
    """The OPEN feature is advertised when the service supports it."""
    lock = AutomationDeviceLock(controller, "5", 0, UID)
    assert lock.supported_features & LockEntityFeature.OPEN


@pytest.mark.parametrize(
    "prop",
    [
        "is_locked",
        "is_locking",
        "is_unlocking",
        "is_jammed",
        "is_opening",
        "is_open",
    ],
)
def test_lock_state_properties(controller: MagicMock, prop: str) -> None:
    """Each lock state property reflects the backing service."""
    lock = AutomationDeviceLock(controller, "5", 0, UID)
    setattr(lock._service, prop, True)
    assert getattr(lock, prop) is True
    setattr(lock._service, prop, False)
    assert getattr(lock, prop) is False


@pytest.mark.parametrize(
    ("method", "service_call"),
    [
        ("async_lock", "lock"),
        ("async_unlock", "unlock"),
        ("async_open", "open"),
    ],
)
async def test_lock_commands(
    controller: MagicMock, method: str, service_call: str
) -> None:
    """Lock/unlock/open forward to the backing service."""
    lock = AutomationDeviceLock(controller, "5", 0, UID)
    setattr(lock._service, service_call, AsyncMock())

    await getattr(lock, method)()

    getattr(lock._service, service_call).assert_awaited_once()
