"""Tests for the Qolsys Panel scenes."""

from unittest.mock import AsyncMock, MagicMock

from conftest import PANEL_MAC
import pytest

from custom_components.qolsys_panel.scene import QolsysPanelScene, async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

UID = PANEL_MAC


@pytest.fixture
def controller() -> MagicMock:
    """A controller mock with one scene and an awaitable execute command."""
    c = MagicMock()
    scene = MagicMock()
    scene.scene_id = "7"
    scene.name = "Good Night"
    c.state.scenes = [scene]
    c.state.scene.return_value = scene
    c.commands.panel.execute_scene = AsyncMock()
    return c


async def test_async_setup_entry_missing_unique_id_raises(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup raises ConfigEntryError when the config entry has no unique_id."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = None
    add_entities = MagicMock()

    with pytest.raises(ConfigEntryError):
        await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_not_called()


async def test_async_setup_entry_creates_entities(
    hass: HomeAssistant, controller: MagicMock
) -> None:
    """Setup builds a scene entity per panel scene."""
    config_entry = MagicMock()
    config_entry.runtime_data = controller
    config_entry.unique_id = UID
    add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], QolsysPanelScene)


def test_name_has_no_device_prefix(controller: MagicMock) -> None:
    """The entity is named after the panel scene, without a device prefix."""
    scene = QolsysPanelScene(controller, "7", UID)
    controller.state.scene.assert_called_once_with("7")
    assert scene.name == "Good Night Scene"
    assert scene.unique_id == f"{UID}_scene_7"


async def test_activate(controller: MagicMock) -> None:
    """Activating the scene executes it on the panel."""
    scene = QolsysPanelScene(controller, "7", UID)
    await scene.async_activate()
    controller.commands.panel.execute_scene.assert_awaited_once_with("7")
