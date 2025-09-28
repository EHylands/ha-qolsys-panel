"""Types for the Qolsys Panel integration."""

from qolsys_controller import qolsys_controller

from homeassistant.config_entries import ConfigEntry

type QolsysPanelConfigEntry = ConfigEntry[qolsys_controller]
