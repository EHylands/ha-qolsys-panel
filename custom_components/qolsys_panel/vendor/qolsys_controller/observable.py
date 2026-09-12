import inspect
import logging
from typing import Any, Protocol

from .enum_qolsys import QolsysNotification

LOGGER = logging.getLogger(__name__)


class Callback(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> None: ...


class Event:
    def __init__(
        self,
        notification: QolsysNotification,
        source: object,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.type: QolsysNotification = notification
        self.data = data or {}
        self.source = source


class QolsysObservable:
    def __init__(self) -> None:
        self._observers: dict[QolsysNotification, list[Callback]] = {}
        self._batch_update_active = False
        self._batch_update_data: dict[QolsysNotification, dict[str, Any]] = {}

    def register(self, notification: QolsysNotification, callback: Callback) -> None:
        callbacks = self._observers.setdefault(notification, [])
        if callback not in callbacks:
            callbacks.append(callback)

    def unregister(self, notification: QolsysNotification, callback: Callback) -> None:
        if notification in self._observers and callback in self._observers[notification]:
            self._observers[notification].remove(callback)

    def _call_callback(self, callback: Callback, event: Event) -> None:
        try:
            signature = inspect.signature(callback)
        except (TypeError, ValueError):
            callback(event)
            return

        has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in signature.parameters.values())

        positional_parameters = [
            p
            for p in signature.parameters.values()
            if p.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]

        if has_varargs or positional_parameters:
            callback(event)
        else:
            callback()

    def _call_callback_safely(self, callback: Callback, event: Event) -> None:
        """Deliver to one observer without letting it break the others.

        Review N6: the M2 fix moved notification onto the reconnect path, where
        run_supervised catches only CancelledError. An observer that raised
        would stop the controller reconnecting while entities sat on their last
        written state - the exact failure M2 was fixed to prevent.
        """
        try:
            self._call_callback(callback, event)
        except Exception:
            LOGGER.exception("Observer for %s raised; continuing", event.type)

    def notify(self, event: Event) -> None:
        notification = event.type

        if self._batch_update_active:
            event_dict = self._batch_update_data.get(notification, {}).copy()
            event_dict.update(event.data)
            self._batch_update_data[notification] = event_dict
        else:
            for callback in self._observers.get(notification, []):
                self._call_callback_safely(callback, event)

    def start_batch_update(self) -> None:
        self._batch_update_data.clear()
        self._batch_update_active = True

    def end_batch_update(self) -> None:
        self._batch_update_active = False
        for event_type, event_data in self._batch_update_data.items():
            event = Event(notification=event_type, source=self, data=event_data)
            for callback in self._observers.get(event_type, []):
                self._call_callback_safely(callback, event)
        self._batch_update_data.clear()

    def cancel_batch_update(self) -> None:
        self._batch_update_active = False
        self._batch_update_data.clear()
