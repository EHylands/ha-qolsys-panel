"""Entities follow the real controller's state (audit L6, C1, M2, M4).

The rest of the entity tests drive a MagicMock controller, so they verify the
entity's own arithmetic but never that the library tells the entity anything.
These drive the real QolsysController.
"""

from conftest import PANEL_MAC

from custom_components.qolsys_panel.entity import QolsysPanelEntity
from custom_components.qolsys_panel.vendor.qolsys_controller.controller import (
    QolsysController,
)
from custom_components.qolsys_panel.vendor.qolsys_controller.enum_qolsys import (
    ControllerState,
)

UID = PANEL_MAC


async def test_entity_goes_unavailable_when_the_panel_drops() -> None:
    """A dropped connection writes the state, and it reads unavailable."""
    controller = QolsysController()
    entity = QolsysPanelEntity(controller, UID)
    writes: list[bool] = []
    entity.async_write_ha_state = lambda: writes.append(entity.available)

    await entity.async_added_to_hass()
    await controller.set_controller_state(ControllerState.CONNECTING)
    await controller.set_controller_state(ControllerState.CONNECTED)
    await controller.set_controller_state(ControllerState.RECONNECTING)

    # One write per transition, and the availability written for RECONNECTING is
    # False - not "still True because the state had not been committed yet".
    assert writes == [False, True, False]
    assert entity.available is False


async def test_entity_stops_following_after_removal() -> None:
    """Removing the entity unregisters it from the controller."""
    controller = QolsysController()
    entity = QolsysPanelEntity(controller, UID)
    writes: list[bool] = []
    entity.async_write_ha_state = lambda: writes.append(entity.available)

    await entity.async_added_to_hass()
    await entity.async_will_remove_from_hass()
    await controller.set_controller_state(ControllerState.CONNECTING)

    assert writes == []
