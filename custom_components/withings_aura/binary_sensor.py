"""Binary sensor platform for the Withings Aura."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import AuraEntity
from .runtime import AuraConfigEntry


async def async_setup_entry(
    hass,
    entry: AuraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([AuraPlayingBinarySensor(entry.runtime_data.coordinator)])


class AuraPlayingBinarySensor(AuraEntity, BinarySensorEntity):
    """Whether a program is currently playing."""

    _attr_translation_key = "playing"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "playing")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.status.playing)
