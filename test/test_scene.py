"""Tests for the Qolsys Panel scenes."""

from unittest.mock import AsyncMock, MagicMock

from conftest import PANEL_MAC
import pytest

from custom_components.qolsys_panel.scene import (
    QolsysPanelScene,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant

UID = PANEL_MAC


@pytest.fixture
def controller() -> MagicMock:
    """A controller mock with one scene and an awaitable execute command."""
    c = MagicMock()
    scene = MagicMock()
    scene.scene_id = "7"
    c.state.scenes = [scene]
    c.commands.panel.execute_scene = AsyncMock()
    return c


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


async def test_activate(controller: MagicMock) -> None:
    """Activating the scene executes it on the panel."""
    scene = QolsysPanelScene(controller, "7", UID)
    await scene.async_activate()
    controller.commands.panel.execute_scene.assert_awaited_once_with("7")
