"""Panel broadcasts (no requestID) and the command queue's handling of strays."""

import asyncio
import logging

import pytest

from custom_components.qolsys_panel.vendor.qolsys_controller.errors import QolsysOperationTimeoutError
from custom_components.qolsys_panel.vendor.qolsys_controller.mqtt_command_queue import QolsysMqttCommandQueue
from custom_components.qolsys_panel.vendor.qolsys_controller.panel_broadcasts import IGNORED_BROADCASTS, QolsysPanelBroadcasts

BC_LOGGER = "custom_components.qolsys_panel.vendor.qolsys_controller.panel_broadcasts"
Q_LOGGER = "custom_components.qolsys_panel.vendor.qolsys_controller.mqtt_command_queue"


def test_known_broadcast_is_ignored_quietly(caplog):
    h = QolsysPanelBroadcasts()
    with caplog.at_level(logging.DEBUG, logger=BC_LOGGER):
        h.handle({"eventName": "splitMessage", "general_data": "A0724456"})
        h.handle({"eventName": "splitMessage", "general_data": "A0724457"})
    assert "splitMessage" in IGNORED_BROADCASTS
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
    assert sum("ignored" in r.getMessage() for r in caplog.records) == 2


def test_unknown_broadcast_warns_once_per_type(caplog):
    h = QolsysPanelBroadcasts()
    with caplog.at_level(logging.DEBUG, logger=BC_LOGGER):
        for _ in range(3):
            h.handle({"eventName": "brandNewThing", "payload": 1})
        h.handle({"eventName": "anotherNewThing"})
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 2
    assert "brandNewThing" in warnings[0] and "IGNORED_BROADCASTS" in warnings[0]
    assert "anotherNewThing" in warnings[1]


@pytest.mark.asyncio
async def test_queue_matches_reply_to_waiter():
    q = QolsysMqttCommandQueue()
    waiter = asyncio.create_task(q.wait_for_response("abc", timeout=2))
    await asyncio.sleep(0)
    await q.handle_response({"requestID": "abc", "ok": True})
    assert (await waiter)["ok"] is True
    assert q.waiters == {}


@pytest.mark.asyncio
async def test_queue_strays_are_debug_not_error(caplog):
    q = QolsysMqttCommandQueue()
    with caplog.at_level(logging.DEBUG, logger=Q_LOGGER):
        await q.handle_response({"eventName": "splitMessage"})          # no requestID: routing regression
        await q.handle_response({"requestID": "nobody-waits"})         # late reply after a timeout
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
    msgs = [r.getMessage() for r in caplog.records]
    assert any("without requestID" in m for m in msgs)
    assert any("late or unmatched" in m for m in msgs)


@pytest.mark.asyncio
async def test_queue_timeout_cleans_up_and_raises():
    q = QolsysMqttCommandQueue()
    with pytest.raises(QolsysOperationTimeoutError):
        await q.wait_for_response("slow", timeout=0.05)
    assert q.waiters == {}
