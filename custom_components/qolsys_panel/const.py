"""Constants for the Qolsys Panel integration."""

DOMAIN = "qolsys_panel"
CONFIG_DIR = "qolsys_panel"

CONF_RANDOM_MAC = "random_mac"
CONF_IMEI = "imei"

OPTION_MOTION_SENSOR_DELAY_ENABLED = "option_motion_sensor_delay_enabled"
OPTION_MOTION_SENSOR_DELAY = "option_motion_sensor_delay"
OPTION_TRIGGER_POLICE = "option_trigger_police"
OPTION_TRIGGER_AUXILLIARY = "option_trigger_auxilliary"
OPTION_TRIGGER_FIRE = "option_trigger_fire"
OPTION_ARM_CODE = "option_arm_code"
OPTION_DISARM_CODE = "option_disarm_code"

SERVICE_TRIGGER_POLICE = "trigger_police"
SERVICE_TRIGGER_AUXILLIARY = "trigger_auxilliary"
SERVICE_TRIGGER_FIRE = "trigger_fire"
SERVICE_QUICK_EXIT = "quick_exit"

DEFAULT_QUICK_EXIT_DURATION = 120

# Arming without a code is normal for an alarm panel and stays opt-in.
DEFAULT_ARM_CODE_REQUIRED = False
# Disarming must not be a one-click action: the panel authenticates the paired
# keypad certificate and never checks a user code itself, so this check, done by
# the integration, is the only thing between a Home Assistant user and a
# disarmed house (audit C1).
DEFAULT_DISARM_CODE_REQUIRED = True
DEFAULT_TRIGGER_POLICE = False
DEFAULT_TRIGGER_AUXILLIARY = False
DEFAULT_TRIGGER_FIRE = False
DEFAULT_MOTION_SENSOR_DELAY_ENABLED = False
DEFAULT_MOTION_SENSOR_DELAY = 310
