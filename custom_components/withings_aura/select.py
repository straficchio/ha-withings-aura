"""Select platform for the Withings Aura program type."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import PROGRAM_OPTIONS, PROGRAM_TYPES
from .entity import AuraEntity
from .runtime import AuraConfigEntry

STATUS_TO_PROGRAM = {
    1: PROGRAM_TYPES[3],  # sleep
    2: PROGRAM_TYPES[4],  # wake-up
    3: PROGRAM_TYPES[2],  # nap
    4: PROGRAM_TYPES[1],  # mood
    6: PROGRAM_TYPES[6],  # media
}


async def async_setup_entry(
    hass,
    entry: AuraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([AuraProgramSelect(entry.runtime_data.coordinator)])


class AuraProgramSelect(AuraEntity, SelectEntity):
    """Choose which program the Start button will launch."""

    _attr_translation_key = "program"
    _attr_options = PROGRAM_OPTIONS
    _attr_icon = "mdi:playlist-music"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "program")

    @property
    def current_option(self) -> str | None:
        if not self.coordinator.data:
            return self.coordinator.selected_program
        return STATUS_TO_PROGRAM.get(
            self.coordinator.data.status.status, self.coordinator.selected_program
        )

    async def async_select_option(self, option: str) -> None:
        self.coordinator.selected_program = option
        self.async_write_ha_state()
        # Let the volume number reflect the newly selected program.
        self.coordinator.async_update_listeners()
