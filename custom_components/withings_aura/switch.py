"""Switch platform for the Withings Aura."""

from __future__ import annotations

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
            AuraClockDisplaySwitch(coordinator),
            AuraPrivateModeSwitch(coordinator),
            AuraAlarmEnabledSwitch(coordinator),
        ]
    )


class AuraClockDisplaySwitch(AuraEntity, SwitchEntity):
    """Enable or disable the Aura clock display."""

    _attr_translation_key = "clock_display"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "clock_display")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.settings.clock_display)

    async def async_turn_on(self, **kwargs) -> None:
        settings = self.coordinator.data.settings
        await self.coordinator.async_set_clock_display(True, settings.clock_brightness)

    async def async_turn_off(self, **kwargs) -> None:
        settings = self.coordinator.data.settings
        await self.coordinator.async_set_clock_display(False, settings.clock_brightness)


class AuraPrivateModeSwitch(AuraEntity, SwitchEntity):
    """Enable or disable Aura private mode."""

    _attr_translation_key = "private_mode"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "private_mode")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.settings.private_mode)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_private_mode(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_private_mode(False)


class AuraAlarmEnabledSwitch(AuraEntity, SwitchEntity):
    """Enable or disable all Aura alarms."""

    _attr_translation_key = "alarm_enabled"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "alarm_enabled")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.alarm_enabled is not None

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.alarm_enabled)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_alarm_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_alarm_enabled(False)
