"""Number platform for the Withings Aura."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import PROGRAM_NAME_TO_TYPE
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
            AuraClockBrightnessNumber(coordinator),
            AuraProgramVolumeNumber(coordinator),
        ]
    )


class AuraClockBrightnessNumber(AuraEntity, NumberEntity):
    """Clock display brightness."""

    _attr_translation_key = "clock_brightness"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "clock_brightness")

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.settings.clock_brightness

    async def async_set_native_value(self, value: float) -> None:
        settings = self.coordinator.data.settings
        await self.coordinator.async_set_clock_display(settings.clock_display, int(value))


class AuraProgramVolumeNumber(AuraEntity, NumberEntity):
    """Volume for the currently selected program type."""

    _attr_translation_key = "program_volume"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:volume-high"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "program_volume")

    def _program_type(self) -> int:
        return PROGRAM_NAME_TO_TYPE[self.coordinator.selected_program]

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        raw = self.coordinator.data.programs.get(self._program_type(), {}).get("1")
        if raw in (None, "", "18446744073709551615"):
            return 50
        try:
            return int(raw)
        except ValueError:
            return 50

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_program_settings(self._program_type(), volume=int(value))
