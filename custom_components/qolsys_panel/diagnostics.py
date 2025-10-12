"""Diagnostics for Qolsys Panel."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant

from .const import CONF_IMEI, CONF_RANDOM_MAC
from .types import QolsysPanelConfigEntry

TO_REDACT = [CONF_IMEI, CONF_RANDOM_MAC, CONF_HOST, CONF_MAC, "name", "sensorname", "node_name", "dimmer_name", "doorlock_name","thermostat_name"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: QolsysPanelConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    QolsysPanel = entry.runtime_data

    if QolsysPanel is None:
        return {"entry_data": async_redact_data(entry.data, TO_REDACT)}

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "data": async_redact_data({
            "android_version": QolsysPanel.panel.ANDROID_VERSION,
            "hardware_version": QolsysPanel.panel.HARDWARE_VERSION,
            "panel_tamper_state": QolsysPanel.panel.PANEL_TAMPER_STATE,
            "ac_status": QolsysPanel.panel.AC_STATUS,
            "battery_status": QolsysPanel.panel.BATTERY_STATUS,
            "gsm_connection_satus": QolsysPanel.panel.GSM_CONNECTION_STATUS,
            "gsm_signal_strength": QolsysPanel.panel.GSM_SIGNAL_STRENGTH,
            "fail_to_communicate": QolsysPanel.panel.FAIL_TO_COMMUNICATE,
            "language": QolsysPanel.panel.LANGUAGE,
            "temp_format": QolsysPanel.panel.TEMPFORMAT,
            "zwave_firmware_version": QolsysPanel.panel.ZWAVE_FIRM_WARE_VERSION,  
            "zwave_card_present": QolsysPanel.panel.ZWAVE_CARD,
            "zwave_controller_enabled": QolsysPanel.panel.ZWAVE_CONTROLLER,
            "partitions_enabled": QolsysPanel.panel.PARTITIONS,
            "control4_enabled": QolsysPanel.panel.CONTROL_4,
            "six_digit_user_code_enabled": QolsysPanel.panel.SIX_DIGIT_USER_CODE,
            "secure_arming": QolsysPanel.panel.SECURE_ARMING,
            "auto_stay": QolsysPanel.panel.AUTO_STAY,
            "auto_bypass": QolsysPanel.panel.AUTO_BYPASS,
            "auto_arm_stay": QolsysPanel.panel.AUTO_ARM_STAY,
            "auto_exit_extension": QolsysPanel.panel.AUTO_EXIT_EXTENSION,
            "final_exit_door_arming": QolsysPanel.panel.FINAL_EXIT_DOOR_ARMING,
            "no_arm_low_battery": QolsysPanel.panel.NO_ARM_LOW_BATTERY,
            "normal_entry_delay": QolsysPanel.panel.TIMER_NORMAL_ENTRY_DELAY,
            "normal_exit_delay": QolsysPanel.panel.TIMER_NORMAL_EXIT_DELAY,
            "long_entry_delay": QolsysPanel.panel.TIMER_LONG_ENTRY_DELAY,
            "long_exit_delay": QolsysPanel.panel.TIMER_LONG_EXIT_DELAY,
            "auxiliary_panic_enabled": QolsysPanel.panel.AUXILIARY_PANIC_ENABLED,
            "fire_panic_enabled": QolsysPanel.panel.FIRE_PANIC_ENABLED,
            "police_panic_enabled": QolsysPanel.panel.POLICE_PANIC_ENABLED,
            "night_mode_settings": QolsysPanel.panel.NIGHTMODE_SETTINGS,
            "night_mode_settings_stage2": QolsysPanel.panel.NIGHT_SETTINGS_STATE,
            "show_security_sensors": QolsysPanel.panel.SHOW_SECURITY_SENSORS,
            "partitions": [
                {
                    "id": partition.id,
                    "name": partition.name,
                    "system_status": partition.system_status,
                    "alarm_state":partition.alarm_state,
                    "alarm_type": partition.alarm_type_array,
                }
                for partition in QolsysPanel.state.partitions
            ],
            "zones": [zone.to_dict() for zone in QolsysPanel.state.zones],
            "zwave_dimmers": [dimmer.to_dict_dimmer() for dimmer in QolsysPanel.state.zwave_dimmers],
            "zwave_locks": [lock.to_dict_lock() for lock in QolsysPanel.state.zwave_locks],
            "zwave_nodes": [device.to_dict_base() for device in QolsysPanel.state.zwave_devices],
        },TO_REDACT)
    }