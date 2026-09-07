"""The controller notifies observers when its state changes (audit M2, L6 item 1)."""

import pytest

from custom_components.qolsys_panel.vendor.qolsys_controller.controller import (
    QolsysController,
)
from custom_components.qolsys_panel.vendor.qolsys_controller.enum_qolsys import (
    ControllerState,
    QolsysNotification,
)
from custom_components.qolsys_panel.vendor.qolsys_controller.errors import (
    InvalidControllerStateTransitionError,
)


def _watch(controller: QolsysController) -> list[ControllerState]:
    """Record the controller state as each notification is delivered."""
    seen: list[ControllerState] = []
    controller.state.register(
        QolsysNotification.PANEL_STATUS_UPDATE,
        lambda *_: seen.append(controller.controller_state),
    )
    return seen


async def test_every_transition_notifies_after_the_state_is_committed() -> None:
    """Observers see the new state, not the one it just left (audit M2)."""
    controller = QolsysController()
    seen = _watch(controller)

    await controller.set_controller_state(ControllerState.CONNECTING)
    await controller.set_controller_state(ControllerState.CONNECTED)
    await controller.set_controller_state(ControllerState.RECONNECTING)

    assert seen == [
        ControllerState.CONNECTING,
        ControllerState.CONNECTED,
        ControllerState.RECONNECTING,
    ]


async def test_a_dropped_connection_reports_reconnecting() -> None:
    """The CONNECTED -> RECONNECTING flip is announced (audit M2).

    This is the transition an alarm entity depends on: miss it and the card
    freezes on a green "Disarmed" while the panel is unreachable.
    """
    controller = QolsysController()
    await controller.set_controller_state(ControllerState.CONNECTING)
    await controller.set_controller_state(ControllerState.CONNECTED)
    seen = _watch(controller)

    await controller.set_controller_state(ControllerState.RECONNECTING)

    assert seen == [ControllerState.RECONNECTING]
    assert controller.controller_state is not ControllerState.CONNECTED


async def test_setting_the_same_state_does_not_notify() -> None:
    """A no-op transition stays a no-op."""
    controller = QolsysController()
    await controller.set_controller_state(ControllerState.CONNECTING)
    seen = _watch(controller)

    await controller.set_controller_state(ControllerState.CONNECTING)

    assert seen == []


async def test_an_invalid_transition_raises_and_does_not_notify() -> None:
    """An impossible transition leaves the state and the observers alone."""
    controller = QolsysController()
    seen = _watch(controller)

    with pytest.raises(InvalidControllerStateTransitionError):
        await controller.set_controller_state(ControllerState.CONNECTED)

    assert seen == []
    assert controller.controller_state is ControllerState.STOPPED
