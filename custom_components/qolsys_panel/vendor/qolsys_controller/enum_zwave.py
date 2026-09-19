from enum import Enum, IntEnum


class MeterType(IntEnum):
    UNKNOWN = 0x00
    ELECTRIC_METER = 0x01
    GAZ_METER = 0x02
    WATER_METER = 0x03
    HEATING = 0x04
    COOLING = 0x05
    RESERVED = 0x6


class MeterRateType(IntEnum):
    UNSPECIFIED = 0x00
    IMPORT = 0x01
    EXPORT = 0x02
    RESERVED = 0x03


class ZWaveMultilevelSensorScale(Enum):
    TEMPERATURE_CELSIUS = "temperature_celsius"
    TEMPERATURE_FAHRENHEIT = "temperature_fahrenheit"
    RELATIVE_HUMIDITY = "relative_humidity"
    WIND_DIRECTION = "wind_direction"
    BAROMETRIC_PRESSURE = "barometric_pressure"
    DEW_POINT = "dew_point"
    RAIN_RATE = "rain_rate"
    TIDE_LEVEL = "tide_level"
    WEIGHT = "weight"
    VOLTS = "volts"
    AMPS = "amps"
    WATTS = "watts"
    DISTANCE = "distance"
    ANGLE_POSITION = "angle_position"
    ROTATION = "rotation"
    WATER_TEMPERATURE_CELSIUS = "water_temperature_celsius"
    WATER_TEMPERATURE_FAHRENHEIT = "water_temperature_fahrenheit"
    LUMINOSITY_LUX = "luminosity_lux"
    UNKNOWN = "unknown"


class ZWaveUnknownMeterScale(IntEnum):
    UNKNOWN = 0


class ZWaveElectricMeterScale(IntEnum):
    KWH = 0
    KVAH = 1
    WATTS = 2
    PULSE_COUNT = 3
    VOLTS = 4
    AMPS = 5
    POWER_FACTOR = 6
    KVAR = 7
    KVARH = 8


class ZWaveGasMeterScale(IntEnum):
    CUBIC_METERS = 0
    CUBIC_FEET = 1
    PULSE_COUNT = 3


class ZWaveWaterMeterScale(IntEnum):
    CUBIC_METERS = 0
    CUBIC_FEET = 1
    US_GALLONS = 2
    PULSE_COUNT = 3


class ZWaveThermalMeterScale(IntEnum):
    KWH = 0
    PULSE_COUNT = 3


class ThermostatMode(IntEnum):
    OFF = 0x00
    HEAT = 0x01
    COOL = 0x02
    AUTO = 0x03
    AUX_HEAT = 0x04
    RESUME = 0x05
    FAN_ONLY = 0x06
    FURNACE = 0x07
    DRY_AIR = 0x08
    MOIST_AIR = 0x09
    AUTO_CHANGEOVER = 0x0A
    ENERGY_SAVE_HEAT = 0x0B
    ENERGY_SAVE_COOL = 0x0C
    AWAY = 0x0F


BITMASK_SUPPORTED_THERMOSTAT_MODE = {
    0: ThermostatMode.OFF,
    1: ThermostatMode.HEAT,
    2: ThermostatMode.COOL,
    3: ThermostatMode.AUTO,
    4: ThermostatMode.AUX_HEAT,
    5: ThermostatMode.RESUME,
    6: ThermostatMode.FAN_ONLY,
    7: ThermostatMode.FURNACE,
}


class ThermostatOperatingState(IntEnum):
    IDLE = 0x00
    HEATING = 0x01
    COOLING = 0x02


class ThermostatSetpointMode(IntEnum):
    HEATING = 0x01
    COOLING = 0x02
    FURNACE = 0x03
    DRY_AIR = 0x04
    MOIST_AIR = 0x05
    AUTO_CHANGEOVER = 0x06
    ECO_HEATING = 0x07
    ECO_COOLING = 0x08
    AWAY_HEATING = 0x09
    AWAY_COOLING = 0x10


BITMASK_SUPPORTED_THERMOSTAT_SETPOINT_MODE = {
    0: ThermostatSetpointMode.HEATING,
    1: ThermostatSetpointMode.COOLING,
    2: ThermostatSetpointMode.FURNACE,
    3: ThermostatSetpointMode.DRY_AIR,
    4: ThermostatSetpointMode.MOIST_AIR,
    5: ThermostatSetpointMode.AUTO_CHANGEOVER,
    6: ThermostatSetpointMode.ECO_HEATING,
    7: ThermostatSetpointMode.ECO_COOLING,
    8: ThermostatSetpointMode.AWAY_HEATING,
    9: ThermostatSetpointMode.AWAY_COOLING,
}


class ThermostatFanMode(IntEnum):
    AUTO_LOW = 0x00
    LOW = 0x01
    AUTO_HIGH = 0x02
    HIGH = 0x03
    AUTO_MEDIUM = 0x04
    MEDIUM = 0x05
    CIRCULATION = 0x06
    HUMIDITY_CIRCULATION = 0x07
    LEFT_RIGHT = 0x08
    UP_DOWN = 0x09
    QUIET = 0x0A
    EXTERNAL_CIRCULATION = 0x0800


BITMASK_SUPPORTED_THERMOSTAT_FAN_MODE = {
    0: ThermostatFanMode.AUTO_LOW,
    1: ThermostatFanMode.LOW,
    2: ThermostatFanMode.AUTO_HIGH,
    3: ThermostatFanMode.HIGH,
    4: ThermostatFanMode.AUTO_MEDIUM,
    5: ThermostatFanMode.MEDIUM,
    6: ThermostatFanMode.CIRCULATION,
    7: ThermostatFanMode.HUMIDITY_CIRCULATION,
}


class ZwaveCommandClass(IntEnum):
    SwitchBinary = 0x25
    SwitchMultilevel = 0x26
    SceneActivation = 0x2B
    SceneActuatorConf = 0x2C
    SensorMultiLevel = 0x31
    Meter = 0x32
    SwitchColor = 0x33
    MeterTableMonitor = 0x3D
    ThermostatMode = 0x40
    ThermostatOperatingState = 0x42
    ThermostatSetPoint = 0x43
    ThermostatFanMode = 0x44
    ThermostatFanState = 0x45
    ClimateControlSchedule = 0x46
    DoorLockLogging = 0x4C
    ScheduleEntryLock = 0x4E
    DeviceResetLocally = 0x5A
    CentralScene = 0x5B
    AssociationGroupInformation = 0x59
    ZWavePlusInfo = 0x5E
    MultiChannel = 0x60
    DoorLock = 0x62
    UserCode = 0x63
    BarrierOperator = 0x66
    Supervision = 0x6C
    EntryControl = 0x6F
    Configuration = 0x70
    Alarm = 0x71
    ManufacturerSpecific = 0x72
    PowerLevel = 0x73
    Protection = 0x75
    SoundSwitch = 0x79
    FirmwareUpdate = 0x7A
    Clock = 0x81
    UserCredential = 0x83
    Association = 0x85
    Version = 0x86
    Indicator = 0x87
    Time = 0x8A
    TimeParameters = 0x8B
    MultiChannelAssociation = 0x8E
    SimpleAVControl = 0x94
    Security = 0x98
    AlarmSensor = 0x9C
    SecurityS2 = 0x9F


class ZwaveCommand(IntEnum):
    SET = 0x01
    GET = 0x02


class ZwaveDeviceClass(Enum):
    Unknown = 0x00
    GenericController = 0x01
    StaticController = 0x02
    AVControlPoint = 0x03
    Display = 0x04
    DoorLock = 0x05
    Thermostat = 0x06
    SensorBinary = 0x07
    SensorMultilevel = 0x08
    Meter = 0x09
    EntryControl = 0x0A
    SemiInteroperable = 0x0B
    Button = 0x0C
    RepeaterSlave = 0x0F
    SwitchBinary = 0x10
    SwitchMultilevel = 0x11
    RemoteSwitchBinary = 0x12
    RemoteSwitchMultilevel = 0x13
    SwitchToggleBinary = 0x14
    SwitchToggleMultilevel = 0x15
    ZIPNode = 0x16
    Ventilation = 0x17
    WindowCovering = 0x18
    BarrierOperator = 0x20
    SensorNotification = 0x21
    SoundSwitch = 0x22
    MeterPulse = 0x23
    ColorSwitch = 0x24
    ClimateControlSchedule = 0x25
    RemoteAssociationActivator = 0x26
    SceneController = 0x27
    SceneSceneActuatorConfiguration = 0x28
    SimpleAVControlPoint = 0x30
