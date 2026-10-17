from typing import Protocol, runtime_checkable


@runtime_checkable
class StatusProtocol(Protocol):
    def supports_status(self) -> bool: ...

    @property
    def is_malfunctioning(self) -> bool: ...
