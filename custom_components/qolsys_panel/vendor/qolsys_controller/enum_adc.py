from enum import Enum, IntEnum


class vdFuncType(IntEnum):
    BINARY_ACTUATOR = 1
    LIGHT = 3
    MALFUNCTION = 10
    DIMMER = 12
    UNKNOWN = 99


class vdFuncName(Enum):
    OPEN_CLOSE = "Open/Close"
    LOCK_UNLOCK = "Lock/Unlock"
    OFF_ON = "Off/On"
    MALFUNCTION = "Malfunction"


class vdFuncLocalControl(IntEnum):
    NONE = 0
    STATUS_ONLY = 1
    FULL_CONTROL = 2


class vdFuncState(IntEnum):
    OFF = 0
    ON = 1
