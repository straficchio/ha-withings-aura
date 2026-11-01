"""Sensor platform for the Withings Aura."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .entity import AuraEntity
from .runtime import AuraConfigEntry
from .util import format_offset


async def async_setup_entry(
    hass,
    entry: AuraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            AuraStatusSensor(coordinator),
            AuraFirmwareSensor(coordinator),
            AuraAlarmCountSensor(coordinator),
            AuraAlarmsSensor(coordinator),
            AuraTimeOffsetSensor(coordinator),
        ]
    )


class AuraStatusSensor(AuraEntity, SensorEntity):
    """Current Aura playback status."""

    _attr_translation_key = "status"
    _attr_icon = "mdi:sleep"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "status")

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.status.name

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data:
            return {}
        status = self.coordinator.data.status
        return {
            "raw_status": status.status,
            "substatus": status.substatus,
            "extra": status.extra.hex(),
        }


class AuraFirmwareSensor(AuraEntity, SensorEntity):
    """Aura firmware version."""

    _attr_translation_key = "firmware"
    _attr_icon = "mdi:chip"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "firmware")

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.probe.firmware


class AuraAlarmCountSensor(AuraEntity, SensorEntity):
    """Number of alarm slots reported by the Aura."""

    _attr_translation_key = "alarm_count"
    _attr_icon = "mdi:alarm-multiple"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "alarm_count")

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.alarm_count


class AuraAlarmsSensor(AuraEntity, SensorEntity):
    """Configured alarms and their settings."""

    _attr_translation_key = "alarms"
    _attr_icon = "mdi:alarm"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "alarms")

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        return len(self.coordinator.data.alarms)

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data:
            return {}
        return {
            "alarm_enabled": self.coordinator.data.alarm_enabled,
            "alarms": [alarm.as_dict() for alarm in self.coordinator.data.alarms],
        }


class AuraTimeOffsetSensor(AuraEntity, SensorEntity):
    """Timezone/UTC offset and the next DST transition sent to the Aura."""

    _attr_translation_key = "time_offset"
    _attr_icon = "mdi:clock-time-four-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "time_offset")

    @property
    def native_value(self) -> str | None:
        info = self.coordinator.time_sync
        if info is not None:
            return str(info["utc_offset_text"])
        offset = dt_util.now().utcoffset()
        return format_offset(int(offset.total_seconds())) if offset is not None else None

    @property
    def extra_state_attributes(self) -> dict:
        info = self.coordinator.time_sync
        if info is None:
            return {}
        return {
            "timezone": info["timezone"],
            "next_dst_change": info["next_change"],
            "next_offset": info["next_offset_text"],
            "synced_at": info["synced_at"],
        }
