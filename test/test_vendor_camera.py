"""Vendored qolsys_controller camera snapshots: upstream v1.11.0 tests/test_camera_commands.py, imports rewritten to the vendored path, otherwise verbatim."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock

import pytest

from custom_components.qolsys_panel.vendor.qolsys_controller.commands.camera import CameraCommands
from custom_components.qolsys_panel.vendor.qolsys_controller.commands.panel import PanelCommands
from custom_components.qolsys_panel.vendor.qolsys_controller.enum_qolsys import PhotoDirectory
from custom_components.qolsys_panel.vendor.qolsys_controller.errors import QolsysOperationError, QolsysSnapshotError
from custom_components.qolsys_panel.vendor.qolsys_controller.media_picture import QolsysPicture
from custom_components.qolsys_panel.vendor.qolsys_controller.mqtt_command import MQTTCommand

if TYPE_CHECKING:
    from custom_components.qolsys_panel.vendor.qolsys_controller.controller import QolsysController


def _make_controller(responder: Callable[[dict[str, Any]], dict[str, Any]]) -> tuple[Any, list[MQTTCommand]]:
    commands: list[MQTTCommand] = []

    async def respond(request_id: str, timeout: int) -> dict[str, Any]:
        return responder(commands[-1]._payload)

    controller = SimpleNamespace(
        settings=SimpleNamespace(mqtt_qos=0, random_mac="02:00:00:00:00:01", _mqtt_command_timeout=30),
        enqueue_mqtt_command=commands.append,
        mqtt_command_queue=SimpleNamespace(wait_for_response=AsyncMock(side_effect=respond)),
    )
    # CameraCommands delegates every transport call to controller.commands.panel,
    # so wire a real PanelCommands over the same mocked MQTT queue.
    controller.commands = SimpleNamespace(panel=PanelCommands(cast("QolsysController", controller)))
    # capture_snapshot publishes the result into state.picture_peek_in (an observable).
    controller.state = SimpleNamespace(picture_peek_in=QolsysPicture())
    return controller, commands


def make_camera(responder: Callable[[dict[str, Any]], dict[str, Any]]) -> tuple[CameraCommands, list[MQTTCommand]]:
    controller, commands = _make_controller(responder)
    return CameraCommands(cast("QolsysController", controller)), commands


def make_panel(responder: Callable[[dict[str, Any]], dict[str, Any]]) -> tuple[PanelCommands, list[MQTTCommand]]:
    controller, commands = _make_controller(responder)
    return controller.commands.panel, commands


async def test_download_accepts_android_line_wrapped_base64() -> None:
    jpeg = b"\xff\xd8sample\xff\xd9"
    encoded = base64.encodebytes(jpeg).decode()
    panel, _ = make_panel(lambda payload: {"photoFrameImageString": encoded})
    assert await panel.download_photo(PhotoDirectory.DISARM.value, "existing.jpg") == jpeg


async def test_iq2_zero_padding_is_removed_after_jpeg_end_marker() -> None:
    jpeg = b"\xff\xd8snapshot\xff\xd9"
    panel, _ = make_panel(lambda payload: {"photoFrameImageString": base64.b64encode(jpeg + b"\x00" * 4096).decode()})
    assert await panel.download_photo(PhotoDirectory.PEEK_IN.value, "existing.jpg") == jpeg


@pytest.mark.parametrize("filename", ["../secret.jpg", "/secret.jpg", "nested/file.jpg", "nested\\file.jpg", "video.mp4"])
async def test_path_rejection_never_sends_a_request(filename: str) -> None:
    panel, commands = make_panel(lambda payload: {})
    with pytest.raises(ValueError):
        await panel.download_photo(PhotoDirectory.PEEK_IN.value, filename)
    assert not commands


async def test_undecodable_base64_download_raises() -> None:
    panel, _ = make_panel(lambda payload: {"photoFrameImageString": "not base64!"})
    with pytest.raises(QolsysOperationError):
        await panel.download_photo(PhotoDirectory.ALARM.value, "saved.jpg")


@pytest.mark.parametrize(
    "encoded",
    [
        base64.b64encode(b"not a JPEG").decode(),
        "/9h0cnVuY2F0ZWQ=",
        base64.b64encode(b"\xff\xd8photo\xff\xd9junk").decode(),
    ],
)
async def test_decodable_non_jpeg_download_returns_none(encoded: str) -> None:
    panel, _ = make_panel(lambda payload: {"photoFrameImageString": encoded})
    assert await panel.download_photo(PhotoDirectory.ALARM.value, "saved.jpg") is None


async def test_capture_uses_callback_filename_instead_of_local_clock() -> None:
    jpeg = b"\xff\xd8fresh\xff\xd9"
    request_id = ""

    def respond(payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal request_id
        if payload["eventName"] == "ipcCall":
            return {"responseStatus": "success"}
        if payload["eventName"] == "photoFrameImageDownloadRequest":
            assert payload["photoFrameImageName"] == request_id + "_1.jpg"
            return {"photoFrameImageString": base64.b64encode(jpeg).decode()}
        if payload["dbOperation"] == "insert":
            metadata = payload["contentValues"]
            request_id = metadata["request_id"]
            assert metadata["user_id"] == -2  # Firmware's local-only sentinel.
            return {"responseStatus": "success", "longValue": "1"}
        return {"resultSet": [{"name": request_id + "_1.jpg"}]}

    camera, commands = make_camera(respond)
    snapshot = await camera.capture_snapshot(retain_on_panel=True)
    assert snapshot.data == jpeg
    assert snapshot.request_id == request_id
    assert snapshot.retained_on_panel
    assert all(c._payload["eventName"] in {"database", "ipcCall", "photoFrameImageDownloadRequest"} for c in commands)


async def test_failed_insert_never_starts_camera() -> None:
    camera, commands = make_camera(lambda payload: {"responseStatus": "success", "longValue": "-1"})
    with pytest.raises(QolsysOperationError, match="metadata"):
        await camera.capture_snapshot()
    assert len(commands) == 1


async def test_capture_timeout_preserves_request_identity() -> None:
    inserted_id = ""

    def respond(payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal inserted_id
        if payload.get("dbOperation") == "insert":
            inserted_id = payload["contentValues"]["request_id"]
            return {"responseStatus": "success", "longValue": "1"}
        if payload["eventName"] == "ipcCall":
            return {"responseStatus": "success"}
        return {"resultSet": []}

    camera, _ = make_camera(respond)
    with pytest.raises(QolsysSnapshotError, match="request ID") as raised:
        await camera.capture_snapshot(timeout=0.01)
    assert raised.value.request_id == inserted_id


async def test_malformed_capture_record_waits_instead_of_crashing() -> None:
    def respond(payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("dbOperation") == "insert":
            return {"responseStatus": "success", "longValue": "1"}
        if payload["eventName"] == "ipcCall":
            return {"responseStatus": "success"}
        return {"resultSet": ["not a record"]}

    camera, _ = make_camera(respond)
    with pytest.raises(QolsysSnapshotError, match="timed out"):
        await camera.capture_snapshot(timeout=0.01)


async def test_default_capture_removes_only_its_generated_file_and_metadata() -> None:
    jpeg = b"\xff\xd8fresh\xff\xd9"
    request_id = ""
    removed = False
    deleted = False

    def respond(payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal request_id, removed, deleted
        if payload["eventName"] == "ipcCall":
            if payload["ipcTransactionID"] == 7:
                assert payload["ipcRequest"][1]["dataValue"] == "../PeekInPhotos/" + request_id + "_123.jpg"
                removed = True
            return {"responseStatus": "success"}
        if payload["eventName"] == "photoFrameImageDownloadRequest":
            return (
                {**payload, "photoFrameImageName": ""}
                if removed
                else {"photoFrameImageString": base64.b64encode(jpeg).decode()}
            )
        if payload["dbOperation"] == "insert":
            request_id = payload["contentValues"]["request_id"]
            return {"responseStatus": "success", "longValue": "1"}
        if payload["dbOperation"] == "delete":
            assert removed  # Never lose the record before confirming file removal.
            assert f"request_id='{request_id}'" in payload["selection"]
            deleted = True
            return {"booleanValue": "true"}
        return {"responseStatus": "success", "resultSet": [] if deleted else [{"name": request_id + "_123.jpg"}]}

    camera, _ = make_camera(respond)
    snapshot = await camera.capture_snapshot()
    assert snapshot.data == jpeg
    assert not snapshot.retained_on_panel
    assert removed and deleted


async def test_failed_file_cleanup_returns_image_and_preserves_metadata() -> None:
    jpeg = b"\xff\xd8fresh\xff\xd9"
    request_id = ""

    def respond(payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal request_id
        if payload["eventName"] == "ipcCall":
            return {"responseStatus": "success"}
        if payload["eventName"] == "photoFrameImageDownloadRequest":
            return {"photoFrameImageString": base64.b64encode(jpeg).decode()}
        if payload["dbOperation"] == "insert":
            request_id = payload["contentValues"]["request_id"]
            return {"responseStatus": "success", "longValue": "1"}
        assert payload["dbOperation"] != "delete"
        return {"resultSet": [{"name": request_id + "_123.jpg"}]}

    camera, _ = make_camera(respond)
    snapshot = await camera.capture_snapshot()
    assert snapshot.data == jpeg
    assert snapshot.retained_on_panel
    assert snapshot.request_id == request_id


async def test_slow_cleanup_does_not_discard_downloaded_image() -> None:
    jpeg = b"\xff\xd8fresh\xff\xd9"
    request_id = ""
    removed = False

    async def slow_cleanup(cleanup_id: str, filename: str) -> None:
        nonlocal removed
        await asyncio.sleep(0.05)
        removed = True

    def respond(payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal request_id
        if payload["eventName"] == "ipcCall":
            return {"responseStatus": "success"}
        if payload["eventName"] == "photoFrameImageDownloadRequest":
            return {"photoFrameImageString": base64.b64encode(jpeg).decode()}
        if payload["dbOperation"] == "insert":
            request_id = payload["contentValues"]["request_id"]
            return {"responseStatus": "success", "longValue": "1"}
        return {"resultSet": [{"name": request_id + "_123.jpg"}]}

    camera, _ = make_camera(respond)
    camera._cleanup_capture = slow_cleanup  # type: ignore[method-assign, assignment]
    snapshot = await camera.capture_snapshot(timeout=0.02)
    assert snapshot.data == jpeg
    assert removed and not snapshot.retained_on_panel


async def test_cleanup_snapshot_recovers_a_completed_capture() -> None:
    request_id = "6f1c1d6e-2b9a-4a35-9d6b-7c2b0f5d1a10"
    removed = deleted = False

    def respond(payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal removed, deleted
        if payload["eventName"] == "ipcCall":
            assert payload["ipcRequest"][1]["dataValue"] == f"../PeekInPhotos/{request_id}_9.jpg"
            removed = True
            return {"responseStatus": "success"}
        if payload["eventName"] == "photoFrameImageDownloadRequest":
            return {**payload, "photoFrameImageName": ""}
        if payload["dbOperation"] == "delete":
            deleted = True
            return {"booleanValue": "true"}
        assert "user_id=-2" in payload["selection"] or deleted
        return {"responseStatus": "success", "resultSet": [] if deleted else [{"name": f"{request_id}_9.jpg"}]}

    camera, _ = make_camera(respond)
    await camera.cleanup_snapshot(request_id)
    assert removed and deleted


async def test_cleanup_snapshot_leaves_an_incomplete_capture() -> None:
    camera, commands = make_camera(lambda payload: {"responseStatus": "success", "resultSet": [{"name": ""}]})
    with pytest.raises(QolsysOperationError, match="not completed"):
        await camera.cleanup_snapshot("6f1c1d6e-2b9a-4a35-9d6b-7c2b0f5d1a10")
    assert [c._payload.get("dbOperation") for c in commands] == ["read"]


async def test_cleanup_tolerates_eventually_consistent_readback(monkeypatch: pytest.MonkeyPatch) -> None:
    jpeg = b"\xff\xd8fresh\xff\xd9"
    request_id = ""
    removed = False
    deleted = False
    file_reads = 0
    row_reads = 0

    monkeypatch.setattr("custom_components.qolsys_panel.vendor.qolsys_controller.commands.camera.asyncio.sleep", AsyncMock())

    def respond(payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal request_id, removed, deleted, file_reads, row_reads
        if payload["eventName"] == "ipcCall":
            removed = True
            return {"responseStatus": "success"}
        if payload["eventName"] == "photoFrameImageDownloadRequest":
            file_reads += 1
            if removed and file_reads > 1:  # stale on first read-back, gone after
                return {**payload, "photoFrameImageName": ""}
            return {"photoFrameImageString": base64.b64encode(jpeg).decode()}
        if payload["dbOperation"] == "insert":
            request_id = payload["contentValues"]["request_id"]
            return {"responseStatus": "success", "longValue": "1"}
        if payload["dbOperation"] == "delete":
            deleted = True
            return {"booleanValue": "true"}
        if payload["dbOperation"] == "read" and deleted:
            row_reads += 1
            return {"responseStatus": "success", "resultSet": [] if row_reads > 1 else [{"name": request_id + "_1.jpg"}]}
        return {"responseStatus": "success", "resultSet": [{"name": request_id + "_1.jpg"}]}

    camera, _ = make_camera(respond)
    snapshot = await camera.capture_snapshot()
    assert snapshot.data == jpeg
    assert not snapshot.retained_on_panel  # the retry confirmed cleanup, not a false failure
    assert removed and deleted and file_reads > 1 and row_reads > 1


async def test_cleanup_snapshot_rejects_arbitrary_selection() -> None:
    camera, commands = make_camera(lambda payload: {})
    with pytest.raises(ValueError):
        await camera.cleanup_snapshot("x' OR '1'='1")
    assert not commands
