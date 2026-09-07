"""Types for the Qolsys Panel integration."""

from homeassistant.config_entries import ConfigEntry

from .vendor.qolsys_controller import qolsys_controller

type QolsysPanelConfigEntry = ConfigEntry[qolsys_controller]
