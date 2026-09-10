import asyncio
import logging
from typing import Any

from .errors import QolsysOperationTimeoutError

LOGGER = logging.getLogger(__name__)


class QolsysMqttCommandQueue:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.waiters: dict[str, asyncio.Future[Any]] = {}

    async def handle_response(self, response: dict[str, str]) -> None:
        requestID = response.get("requestID")

        if not requestID:
            # Broadcasts are routed elsewhere by the controller; reaching here means a
            # routing regression, worth a debug line, never an error per message.
            LOGGER.debug("MQTT Command response without requestID reached the queue: %s", response.get("eventName"))
            return

        async with self.lock:
            future = self.waiters.pop(requestID, None)

        if future is None:
            # A reply nobody waits for any more: the command timed out or was cancelled.
            LOGGER.debug("MQTT Command late or unmatched response for requestID %s", requestID)
            return
        if not future.done():
            future.set_result(response)

    async def wait_for_response(self, request_id: str, timeout: int = 30) -> dict[str, Any]:
        future = asyncio.get_running_loop().create_future()
        async with self.lock:
            if request_id == "":
                raise ValueError("request_id cannot be empty")

            if request_id in self.waiters:
                msg = f"Duplicate waiter for request_id: {request_id}"
                raise ValueError(msg)

            self.waiters[request_id] = future

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            LOGGER.debug("MQTT Command timed out for request_id: %s", request_id)
            raise QolsysOperationTimeoutError from None

        finally:
            # Ensure cleanup even if timeout or cancellation happens
            async with self.lock:
                self.waiters.pop(request_id, None)

    def fail_waiter(self, request_id: str, exc: BaseException) -> None:
        future = self.waiters.pop(request_id, None)
        if future and not future.done():
            future.set_exception(exc)

    def fail_all_pending(self, exc: BaseException) -> None:
        pending = self.waiters
        self.waiters = {}
        for future in pending.values():
            if not future.done():
                future.set_exception(exc)
