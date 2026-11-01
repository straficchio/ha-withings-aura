"""Time platform for Withings Aura alarm slots."""

from __future__ import annotations

from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .alarm import async_save_alarm
from .entity import AuraEntity
from .runtime import AuraConfigEntry


async def async_setup_entry(
    hass,
    entry: AuraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    configured = {alarm.slot for alarm in coordinator.data.alarms}
    async_add_entities(
        AuraAlarmTime(coordinator, slot, enabled_default=slot in configured or slot == 1)
        for slot in range(1, 11)
    )


class AuraAlarmTime(AuraEntity, TimeEntity):
    """Time of one alarm slot."""

    _attr_translation_key = "alarm_time"
    _attr_icon = "mdi:alarm"

    def __init__(self, coordinator, slot: int, *, enabled_default: bool) -> None:
        super().__init__(coordinator, f"alarm_{slot}_time")
        self.slot = slot
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_translation_placeholders = {"slot": str(slot)}

    @property
    def _alarm(self):
        if not self.coordinator.data:
            return None
        return next(
            (alarm for alarm in self.coordinator.data.alarms if alarm.slot == self.slot),
            None,
        )

    @property
    def native_value(self) -> dt_time | None:
        alarm = self._alarm
        return dt_time(alarm.hour, alarm.minute) if alarm else None

    async def async_set_value(self, value: dt_time) -> None:
        await async_save_alarm(
            self.coordinator,
            self.slot,
            self._alarm,
            hour=value.hour,
            minute=value.minute,
        )
