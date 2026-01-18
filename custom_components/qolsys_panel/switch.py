"""Switch platform for Qolsys Panel."""

from __future__ import annotations

from typing import Any

from qolsys_controller import qolsys_controller

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import QolsysPanelConfigEntry
from .entity import QolsysPartitionEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QolsysPanelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch."""
    QolsysPanel = config_entry.runtime_data

    entities: list[SwitchEntity] = []

    for partition in QolsysPanel.state.partitions:
        switch_exit_sounds = PartitionSwitch_ExitSounds(
            QolsysPanel, partition.id, config_entry.unique_id
        )
        switch_arm_instant_stay = PartitionSwitch_ArmStayInstant(
            QolsysPanel, partition.id, config_entry.unique_id
        )
        switch_silent_disarming = PartitionSwitch_SilentDisarming(
            QolsysPanel, partition.id, config_entry.unique_id
        )
        switch_entry_delay = PartitionSwitch_EntryDelay(
            QolsysPanel, partition.id, config_entry.unique_id
        )
        entities.append(switch_exit_sounds)
        entities.append(switch_arm_instant_stay)
        entities.append(switch_silent_disarming)
        entities.append(switch_entry_delay)

    async_add_entities(entities)


class PartitionSwitch_ExitSounds(QolsysPartitionEntity, SwitchEntity, RestoreEntity):
    """A switch entity for partition exit sounds."""

    def __init__(
        self, QolsysPanel: qolsys_controller, partition_id: int, unique_id: str
    ) -> None:
        """Set up a switch entity for a partition exit sounds."""
        super().__init__(QolsysPanel, partition_id, unique_id)
        self._attr_unique_id = f"{self._partition_unique_id}_arming_exit_sounds"
        self._attr_name = "Exit Sounds"
        self._attr_device_class = SwitchDeviceClass.SWITCH

    async def async_added_to_hass(self) -> None:
        """Restore previous state on restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()

        if last_state and last_state.state == "on":
            self._partition.command_exit_sounds = True
        else:
            self._partition.command_exit_sounds = False

    @property
    def is_on(self) -> bool:
        """Return if the switch is on."""
        return self._partition.command_exit_sounds

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._partition.command_exit_sounds = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._partition.command_exit_sounds = False


class PartitionSwitch_EntryDelay(QolsysPartitionEntity, SwitchEntity, RestoreEntity):
    """A switch entity for partition entry_delay."""

    def __init__(
        self, QolsysPanel: qolsys_controller, partition_id: int, unique_id: str
    ) -> None:
        """Set up a switch entity for a partition entry_delay."""
        super().__init__(QolsysPanel, partition_id, unique_id)
        self._attr_unique_id = f"{self._partition_unique_id}_command_arm_entry_delay"
        self._attr_name = "Entry Delay"
        self._attr_device_class = SwitchDeviceClass.SWITCH

    async def async_added_to_hass(self) -> None:
        """Restore previous state on restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()

        if last_state and last_state.state == "on":
            self._partition.command_arm_entry_delay = True
        else:
            self._partition.command_arm_entry_delay = False

    @property
    def is_on(self) -> bool:
        """Return if the switch is on."""
        return self._partition.command_arm_entry_delay

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._partition.command_arm_entry_delay = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._partition.command_arm_entry_delay = False


class PartitionSwitch_ArmStayInstant(
    QolsysPartitionEntity, SwitchEntity, RestoreEntity
):
    """A switch entity for partition exit sounds."""

    def __init__(
        self, QolsysPanel: qolsys_controller, partition_id: int, unique_id: str
    ) -> None:
        """Set up a switch entity for a partition exit sounds."""
        super().__init__(QolsysPanel, partition_id, unique_id)
        self._attr_unique_id = f"{self._partition_unique_id}_arm_stay_instant"
        self._attr_name = "Arm Stay Instant"
        self._attr_device_class = SwitchDeviceClass.SWITCH

    async def async_added_to_hass(self) -> None:
        """Restore previous state on restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()

        if last_state and last_state.state == "on":
            self._partition.command_arm_stay_instant = True
        else:
            self._partition.command_arm_stay_instant = False

    @property
    def is_on(self) -> bool:
        """Return if the switch is on."""
        return self._partition.command_arm_stay_instant

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._partition.command_arm_stay_instant = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._partition.command_arm_stay_instant = False


class PartitionSwitch_SilentDisarming(
    QolsysPartitionEntity, SwitchEntity, RestoreEntity
):
    """A switch entity for partition silent disarming."""

    def __init__(
        self, QolsysPanel: qolsys_controller, partition_id: int, unique_id: str
    ) -> None:
        """Set up a switch entity for a partition silent disarming."""
        super().__init__(QolsysPanel, partition_id, unique_id)
        self._attr_unique_id = f"{self._partition_unique_id}_arm_stay_silent_disarming"
        self._attr_name = "Arm Stay Silent Disarming"
        self._attr_device_class = SwitchDeviceClass.SWITCH

    async def async_added_to_hass(self) -> None:
        """Restore previous state on restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()

        if last_state and last_state.state == "on":
            self._partition.command_arm_stay_silent_disarming = True
        else:
            self._partition.command_arm_stay_silent_disarming = False

    @property
    def is_on(self) -> bool:
        """Return if the switch is on."""
        return self._partition.command_arm_stay_silent_disarming

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._partition.command_arm_stay_silent_disarming = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._partition.command_arm_stay_silent_disarming = False
