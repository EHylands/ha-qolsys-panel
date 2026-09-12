from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..automation.device import QolsysAutomationDevice


@runtime_checkable
class ServiceProtocol(Protocol):
    @property
    def automation_device(self) -> "QolsysAutomationDevice": ...

    @automation_device.setter
    def automation_device(self, value: "QolsysAutomationDevice") -> None: ...

    @property
    def endpoint(self) -> int: ...

    @endpoint.setter
    def endpoint(self, value: int) -> None: ...

    @property
    def service_name(self) -> str: ...
