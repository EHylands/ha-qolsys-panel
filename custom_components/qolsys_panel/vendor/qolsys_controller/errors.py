import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


class QolsysError(Exception):
    """Base exception for all Qolsys errors."""

    pass


class InvalidControllerStateTransitionError(Exception):
    pass


#
# Generic operational errors
#
class QolsysOperationError(QolsysError):
    """Base exception for Qolsys operation failures."""

    pass


class QolsysOperationTimeoutError(QolsysOperationError):
    def __init__(self, operation: str | None = None) -> None:
        self.operation = operation

        message = "Operation timed out"
        if operation:
            message = f"Operation timed out: {operation}"

        super().__init__(message)


class QolsysInvalidPartitionIdError(QolsysOperationError):
    """Raised when an invalid partition ID is supplied."""

    def __init__(self, partition_id: str | int) -> None:
        self.partition_id = partition_id
        super().__init__(f"Invalid partition ID: {partition_id}")


class QolsysUserCodeError(QolsysOperationError):
    """Raised when an invalid user code is supplied."""

    def __init__(self) -> None:
        super().__init__("Invalid user code")


class QolsysZoneBypassError(QolsysOperationError):
    """Raised when one or more zones fail to bypass."""

    def __init__(self, zones: list[str]) -> None:
        self.zones = zones
        super().__init__(f"Failed to bypass zones: {', '.join(zones)}")


class CommandExecutionError(QolsysOperationError):
    """Raised when a command execution fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


#
# Network / communication errors
#
class QolsysSslError(QolsysError):
    """Raised for SSL/TLS related failures."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or "SSL error")


class QolsysMqttError(QolsysError):
    """Raised for MQTT related failures."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or "MQTT error")


#
# Configuration / persistence errors
#
class QolsysConfigError(QolsysError):
    """Raised for invalid configuration."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Configuration error: {message}")


class QolsysSqlError(QolsysError):
    """Raised for SQL/database operation failures."""

    def __init__(self, operation: dict[str, Any]) -> None:
        self.operation = operation

        super().__init__(f"SQL error on table '{operation.get('table', 'unknown')}'")

        LOGGER.exception(
            ("SQL operation failed\ntable=%s\nquery=%s\ncolumns=%s\ncontent_values=%s\nselection=%s\nselection_argument=%s"),
            operation.get("table", ""),
            operation.get("query", ""),
            operation.get("columns", ""),
            operation.get("content_value", ""),
            operation.get("selection", ""),
            operation.get("selection_argument", ""),
        )


#
# Device / endpoint errors
#
class InvalidVirtualNodeError(QolsysOperationError):
    """Raised when a virtual node id is invalid."""

    def __init__(self, node_id: str | int) -> None:
        self.node_id = node_id
        super().__init__(f"Invalid virtual_node_id: {node_id}")


class InvalidEndpointError(QolsysOperationError):
    """Raised when an endpoint is invalid for a node."""

    def __init__(self, node_id: str | int, endpoint: str | int) -> None:
        self.node_id = node_id
        self.endpoint = endpoint

        super().__init__(f"Invalid endpoint {endpoint} for node {node_id}")


class ServiceNotFoundError(QolsysOperationError):
    """Raised when a required service is missing."""

    def __init__(
        self,
        node_id: str | int,
        endpoint: str | int,
        service_type: str,
    ) -> None:
        self.node_id = node_id
        self.endpoint = endpoint
        self.service_type = service_type

        super().__init__(f"No service '{service_type}' for node {node_id} endpoint {endpoint}")
