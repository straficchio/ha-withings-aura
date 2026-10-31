"""Button platform for the Withings Aura."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_PROGRAM_IDS, PROGRAM_NAME_TO_TYPE
from .entity import AuraEntity
from .runtime import AuraConfigEntry


async def async_setup_entry(
    hass,
    entry: AuraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            AuraStartProgramButton(coordinator),
            AuraTriggerAlarmButton(coordinator),
            AuraStopProgramButton(coordinator),
            AuraSnoozeButton(coordinator),
            AuraSyncTimeButton(coordinator),
        ]
    )


class AuraStartProgramButton(AuraEntity, ButtonEntity):
    """Start the program selected by the program select entity."""

    _attr_translation_key = "start_program"
    _attr_icon = "mdi:play"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "start_program")

    async def async_press(self) -> None:
        option = self.coordinator.selected_program
        program_type = PROGRAM_NAME_TO_TYPE[option]
        await self.coordinator.async_start_program(
            program_type, DEFAULT_PROGRAM_IDS.get(program_type, 0)
        )


class AuraTriggerAlarmButton(AuraEntity, ButtonEntity):
    """Trigger a wake-up alarm immediately."""

    _attr_translation_key = "trigger_alarm"
    _attr_icon = "mdi:alarm-light"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "trigger_alarm")

    async def async_press(self) -> None:
        await self.coordinator.async_start_program(4, 15)


class AuraStopProgramButton(AuraEntity, ButtonEntity):
    """Stop the current program."""

    _attr_translation_key = "stop_program"
    _attr_icon = "mdi:stop"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "stop_program")

    async def async_press(self) -> None:
        await self.coordinator.async_stop_program()


class AuraSnoozeButton(AuraEntity, ButtonEntity):
    """Snooze the current wake-up."""

    _attr_translation_key = "snooze"
    _attr_icon = "mdi:alarm-snooze"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "snooze")

    async def async_press(self) -> None:
        await self.coordinator.async_snooze()


class AuraSyncTimeButton(AuraEntity, ButtonEntity):
    """Push the Home Assistant time to the Aura."""

    _attr_translation_key = "sync_time"
    _attr_icon = "mdi:clock-check"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "sync_time")

    async def async_press(self) -> None:
        await self.coordinator.async_sync_time()
