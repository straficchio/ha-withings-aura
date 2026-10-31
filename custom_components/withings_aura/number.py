"""Number platform for the Withings Aura."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import AuraEntity
from .runtime import AuraConfigEntry


async def async_setup_entry(
    hass,
    entry: AuraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([AuraClockBrightnessNumber(entry.runtime_data.coordinator)])


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
