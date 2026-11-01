"""Light platform for the Withings Aura."""

from __future__ import annotations

import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .entity import AuraEntity
from .protocol import lamp_channels
from .runtime import AuraConfigEntry

_LOGGER = logging.getLogger(__name__)

DEFAULT_RGB = (255, 180, 107)
DEBOUNCE_SECONDS = 0.5


async def async_setup_entry(
    hass,
    entry: AuraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([AuraLampLight(entry.runtime_data.coordinator)])


class AuraLampLight(AuraEntity, LightEntity):
    """The Aura mood light."""

    _attr_translation_key = "lamp"
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "lamp")
        self._pending: tuple[int, int, int, bool] | None = None
        self._cancel_debounce = None
        self._last_rgb = DEFAULT_RGB

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data and self.coordinator.data.lamp.is_on)

    @property
    def brightness(self) -> int | None:
        """Return HA brightness (0-255), not the Aura percentage."""
        if not self.coordinator.data:
            return None
        return round(self.coordinator.data.lamp.brightness * 255 / 100)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        if not self.coordinator.data:
            return None
        normalized = self.coordinator.data.lamp.normalized_rgb
        return normalized if any(normalized) else self._last_rgb

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the lamp on, optionally changing colour/brightness."""
        current = self.coordinator.data.lamp if self.coordinator.data else None
        rgb = kwargs.get(ATTR_RGB_COLOR)
        if rgb is None:
            normalized = current.normalized_rgb if current else (0, 0, 0)
            rgb = normalized if any(normalized) else self._last_rgb
        rgb = tuple(rgb)
        self._last_rgb = rgb
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is None:
            brightness_percent = current.brightness if current and current.brightness else 100
        else:
            brightness_percent = round(brightness * 100 / 255)
        red, green, blue = lamp_channels(rgb, brightness_percent)
        self._queue(red, green, blue, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the lamp off while preserving the last colour and brightness."""
        current = self.coordinator.data.lamp if self.coordinator.data else None
        if current is not None and any((current.red, current.green, current.blue)):
            self._queue(current.red, current.green, current.blue, False)
        else:
            self._queue(0, 0, 0, False)

    @callback
    def _queue(self, red: int, green: int, blue: int, on: bool) -> None:
        self._pending = (red, green, blue, on)
        self.coordinator.async_update_lamp(red, green, blue, on)
        if self._cancel_debounce is not None:
            self._cancel_debounce()
        self._cancel_debounce = async_call_later(self.hass, DEBOUNCE_SECONDS, self._schedule_commit)

    @callback
    def _schedule_commit(self, _now) -> None:
        self._cancel_debounce = None
        self.hass.async_create_task(self._async_commit())

    async def _async_commit(self) -> None:
        pending = self._pending
        self._pending = None
        if pending is None:
            return
        await self.coordinator.async_set_lamp(*pending)

    async def async_will_remove_from_hass(self) -> None:
        if self._cancel_debounce is not None:
            self._cancel_debounce()
            self._cancel_debounce = None
        self._pending = None
        await super().async_will_remove_from_hass()
