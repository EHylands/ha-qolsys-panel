"""Services for the Qolsys Panel integration."""

from __future__ import annotations

import voluptuous as vol


from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.helpers import service, entity_registry


from custom_components.qolsys_panel import entity

from .const import (
    DOMAIN,
    SERVICE_TRIGGER_POLICE,
    SERVICE_TRIGGER_AUXILLIARY,
    SERVICE_TRIGGER_FIRE,
)
from .types import QolsysPanelConfigEntry


async def async_trigger_police(ent: entity, call: ServiceCall) -> None:
    """Trigger Police Alarm on Qolsys Panel."""
    entity_id: str | None = ent.entity_id

    # Get the entity registry entry
    er = entity_registry.async_get(call.hass)
    entry = er.async_get(entity_id)
    if entry is None:
        raise ValueError(f"Entity {entity_id} not found in registry")

    # Get the config entry associated with the entity
    config_entry: QolsysPanelConfigEntry | None = (
        call.hass.config_entries.async_get_entry(entry.config_entry_id)
    )
    if config_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="integration_not_found",
            translation_placeholders={"target": entity_id},
        )

    if config_entry.state is not ConfigEntryState.LOADED:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
            translation_placeholders={"target": config_entry.title},
        )

    QolsysPanel = config_entry.runtime_data
    partition_id: str = ent._partition_id
    silent: bool = call.data.get("silent")
    await QolsysPanel.command_panel_trigger_police(
        partition_id=partition_id, silent=silent
    )


async def async_trigger_auxilliary(ent: entity, call: ServiceCall) -> None:
    """Trigger Auxilliary Alarm on Qolsys Panel."""
    entity_id: str | None = ent.entity_id

    # Get the entity registry entry
    er = entity_registry.async_get(call.hass)
    entry = er.async_get(entity_id)
    if entry is None:
        raise ValueError(f"Entity {entity_id} not found in registry")

    # Get the config entry associated with the entity
    config_entry: QolsysPanelConfigEntry | None = (
        call.hass.config_entries.async_get_entry(entry.config_entry_id)
    )
    if config_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="integration_not_found",
            translation_placeholders={"target": entity_id},
        )

    if config_entry.state is not ConfigEntryState.LOADED:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
            translation_placeholders={"target": config_entry.title},
        )

    QolsysPanel = config_entry.runtime_data
    partition_id: str = ent._partition_id
    silent: bool = call.data.get("silent")
    await QolsysPanel.command_panel_trigger_auxilliary(
        partition_id=partition_id, silent=silent
    )


async def async_trigger_fire(ent: entity, call: ServiceCall) -> None:
    """Trigger Fire Alarm on Qolsys Panel."""
    entity_id: str | None = ent.entity_id

    # Get the entity registry entry
    er = entity_registry.async_get(call.hass)
    entry = er.async_get(entity_id)
    if entry is None:
        raise ValueError(f"Entity {entity_id} not found in registry")

    # Get the config entry associated with the entity
    config_entry: QolsysPanelConfigEntry | None = (
        call.hass.config_entries.async_get_entry(entry.config_entry_id)
    )
    if config_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="integration_not_found",
            translation_placeholders={"target": entity_id},
        )

    if config_entry.state is not ConfigEntryState.LOADED:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
            translation_placeholders={"target": config_entry.title},
        )

    QolsysPanel = config_entry.runtime_data
    partition_id: str = ent._partition_id
    await QolsysPanel.command_panel_trigger_fire(partition_id=partition_id)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Qolsys Panel integration."""

    # Trigger Police Service
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_TRIGGER_POLICE,
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        schema={
            vol.Required("silent"): cv.boolean,
        },
        func=async_trigger_police,
    )

    # Trigger Auxilliary Service
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_TRIGGER_AUXILLIARY,
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        schema={
            vol.Required("silent"): cv.boolean,
        },
        func=async_trigger_auxilliary,
    )

    # Trigger Fire Service
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_TRIGGER_FIRE,
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        schema={},
        func=async_trigger_fire,
    )
