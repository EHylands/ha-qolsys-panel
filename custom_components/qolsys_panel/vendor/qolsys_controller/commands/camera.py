"""Opt-in local panel-camera snapshots."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..enum_qolsys import PhotoDirectory
from ..errors import QolsysOperationError, QolsysSnapshotError
from ..media_picture import QolsysPicture

if TYPE_CHECKING:
    from ..controller import QolsysController

_CAMERA_URI = "content://com.qolsys.qolsysprovider.CameraRequestContentProvider/camerarequest"

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CameraSnapshot:
    """Downloaded JPEG and its panel request's identity."""

    jpeg: bytes
    request_id: str
    filename: str
    retained_on_panel: bool


class CameraCommands:
    """Request-driven still images; this does not enable continuous recording."""

    def __init__(self, controller: QolsysController) -> None:
        self._controller = controller
        self._capture_lock = asyncio.Lock()

    async def _verify(self, condition: Callable[[], Awaitable[bool]], attempts: int = 5, delay: float = 1) -> bool:
        """Poll an eventually-consistent panel read until it confirms, bounded.

        The panel's content provider is not read-after-write consistent, so a
        delete can still read back briefly. Retry the verification before failing.
        """
        for attempt in range(attempts):
            if await condition():
                return True
            if attempt + 1 < attempts:
                await asyncio.sleep(delay)
        return False

    async def _cleanup_capture(self, request_id: str, filename: str) -> None:
        """Remove only the generated photo and its own local-only metadata."""
        if not re.fullmatch(re.escape(request_id) + r"_[0-9]+\.jpg", filename):
            raise QolsysOperationError("Unexpected snapshot filename; cleanup stopped")
        # IQ2 transaction 7 only exposes Alarmphotos and AlarmVideos roots.
        # Its named-file remove can reach the adjacent PeekInPhotos directory.
        # This fixed relative prefix is never supplied by an API caller.
        response = await self._controller.commands.panel.delete_photo(filename)
        if response.get("responseStatus") != "success":
            raise QolsysOperationError("Panel refused snapshot file cleanup")

        async def file_absent() -> bool:
            # Presence is read from the raw panel response, not decoded bytes, so a
            # present-but-unreadable file is never mistaken for a deleted one (which
            # would drop the metadata while the image still lingers on the panel).
            return not await self._controller.commands.panel.photo_exists(PhotoDirectory.PEEK_IN.value, filename)

        if not await self._verify(file_absent):
            raise QolsysOperationError("Snapshot file cleanup could not be verified; metadata retained")

        await self._controller.commands.panel.database_remote_delete(
            _CAMERA_URI, f"request_id='{request_id}' AND user_id=-2 AND description='Local snapshot'"
        )

        async def row_absent() -> bool:
            check = await self._controller.commands.panel.database_remote_read(
                uri=_CAMERA_URI,
                projection="[name]",
                selection=f"request_id='{request_id}' AND user_id=-2 AND description='Local snapshot'",
            )
            return check.get("responseStatus") == "success" and check.get("resultSet") == []

        if not await self._verify(row_absent):
            raise QolsysOperationError("Snapshot metadata cleanup could not be verified")

    async def _wait_for_capture(self, request_id: str) -> str:
        """Follow the panel's callback filename instead of guessing from clocks."""
        # Unbounded by design: always awaited inside capture_snapshot's asyncio.timeout,
        # which cancels this poll if the panel never reports a filename.
        while True:
            response = await self._controller.commands.panel.database_remote_read(
                uri=_CAMERA_URI,
                projection="[name]",
                selection=f"request_id='{request_id}'",
            )

            records = response.get("resultSet") or []
            filename = (
                records[0].get("name") if isinstance(records, list) and records and isinstance(records[0], dict) else None
            )
            if filename:
                if not isinstance(filename, str) or not re.fullmatch(re.escape(request_id) + r"_[0-9]+\.jpg", filename):
                    raise QolsysOperationError("Panel returned an unrelated capture filename")
                return filename
            await asyncio.sleep(1)

    async def capture_snapshot(self, *, timeout: float = 20, retain_on_panel: bool = False) -> QolsysPicture:
        """Capture and retrieve a new Peek-In image, then clean up its panel copy.

        Each call creates one camera-request record and saved image. No background
        polling or live stream is started. Firmware 2.8.1's user_id=-2 sentinel
        suppresses ADC upload. Set retain_on_panel=True to keep the panel copy.
        The timeout bounds capture and download, not cleanup. If cleanup fails,
        the downloaded image is still returned with retained_on_panel=True; pass
        its request_id to cleanup_snapshot to retry. A failed or interrupted
        capture raises QolsysSnapshotError carrying the request ID.
        """
        if timeout <= 0:
            raise ValueError("Snapshot timeout must be positive")
        # Serialize the shared panel camera across the whole operation, including the
        # best-effort cleanup below: the panel's camera service handles one request at a
        # time, so a capture must not overlap another capture's capture/delete calls.
        async with self._capture_lock:
            LOGGER.debug("Requesting a new snapshot with timeout %s seconds", timeout)
            request_id = str(uuid.uuid4())
            now = int(time.time() * 1000)
            metadata = {
                "request_id": request_id,
                "type": "PEEK_IN",
                "file_type": "IMAGE",
                "description": "Local snapshot",
                "create_time": now,
                "update_time": now,
                "partition_id": 0,
                "user_id": -2,
                "zone_id": 0,
                "camera_source": 129,
                "imageId": 0,
                "source": "Panel",
            }
            try:
                async with asyncio.timeout(timeout):
                    # Create database record for the new snapshot request, which the panel will fulfill.
                    response = await self._controller.commands.panel.database_remote_insert(
                        uri=_CAMERA_URI,
                        content_values=metadata,
                    )

                    if response.get("responseStatus") != "success":
                        raise QolsysOperationError("Panel rejected the snapshot request metadata insert")

                    if str(response.get("longValue")) != "1":
                        raise QolsysOperationError("Snapshot request metadata insert did not create exactly one row")

                    # Capture snapshot
                    response = await self._controller.commands.panel.capture_photo(request_id, "/sdcard/PeekInPhotos")
                    if response.get("responseStatus") != "success":
                        raise QolsysOperationError("Panel refuse to capture snapshot request")

                    filename = await self._wait_for_capture(request_id)
                    jpeg = await self._controller.commands.panel.download_photo(PhotoDirectory.PEEK_IN.value, filename)

                    if jpeg is None:
                        raise QolsysOperationError("Panel failed to provide snapshot image data")

            except TimeoutError as error:
                raise QolsysSnapshotError("Snapshot timed out", request_id) from error
            except QolsysOperationError as error:
                raise QolsysSnapshotError(str(error), request_id) from error
            if retain_on_panel:
                snapshot = QolsysPicture(data=jpeg, request_id=request_id, filename=filename, retained_on_panel=True)
            else:
                try:
                    await self._cleanup_capture(request_id, filename)
                    snapshot = QolsysPicture(data=jpeg, request_id=request_id, filename=filename, retained_on_panel=False)
                except QolsysOperationError:
                    LOGGER.warning("Snapshot %s was downloaded, but its panel copy remains", request_id, exc_info=True)
                    snapshot = QolsysPicture(data=jpeg, request_id=request_id, filename=filename, retained_on_panel=True)

            # Update internal copy of last peek in picture on main panel and send updates
            self._controller.state.picture_peek_in.update(snapshot)

            return snapshot

    async def cleanup_snapshot(self, request_id: str) -> None:
        """Remove a snapshot this API created, using the request ID it reported.

        Records not created by capture_snapshot are never matched. A capture the
        panel has not completed yet is left in place; retry after it finishes.
        """
        if str(uuid.UUID(request_id)) != request_id:
            raise ValueError("A snapshot request ID is required")
        async with self._capture_lock:
            response = await self._controller.commands.panel.database_remote_read(
                uri=_CAMERA_URI,
                projection="[name]",
                selection=f"request_id='{request_id}' AND user_id=-2 AND description='Local snapshot'",
            )
            records = response.get("resultSet")
            if response.get("responseStatus") != "success" or not isinstance(records, list):
                raise QolsysOperationError("Snapshot metadata could not be read")
            if not records:
                return
            filename = records[0].get("name") if isinstance(records[0], dict) else None
            if not filename:
                raise QolsysOperationError("Snapshot capture has not completed; retry cleanup later")
            await self._cleanup_capture(request_id, filename)
