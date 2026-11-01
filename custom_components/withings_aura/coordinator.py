"""Coordinator for the Withings Aura integration."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import replace
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_POLL_INTERVAL,
    DEFAULT_SLOW_POLL_INTERVAL,
    DOMAIN,
    PROGRAM_TYPES,
)
from .device import AuraDevice
from .exceptions import AuraError
from .models import AuraSettings, AuraSnapshot, LampState, ProbeInfo
from .protocol import ProbeChallengeError
from .util import time_sync_info

_LOGGER = logging.getLogger(__name__)


class AuraCoordinator(DataUpdateCoordinator[AuraSnapshot]):
    """Poll the Aura and serialize all writes."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: AuraDevice,
        *,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        slow_poll_interval: int = DEFAULT_SLOW_POLL_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self.config_entry = entry
        self.device = device
        self.slow_poll_interval = slow_poll_interval
        self._probe: ProbeInfo | None = None
        self._alarms: tuple = ()
        self._alarm_count: int | None = None
        self._alarm_enabled: bool | None = None
        self._programs: dict[int, dict[str, str]] = {}
        self._program_infos: dict[int, Any] = {}
        self._last_slow = 0.0
        self.selected_program: str = PROGRAM_TYPES[1]
        self.time_sync: dict[str, object] | None = None
        self._lamp_write_until = 0.0

    async def _async_update_data(self) -> AuraSnapshot:
        try:
            if self._probe is None:
                self._probe = await self.device.probe()
            status = await self.device.status()
            lamp = await self.device.lamp()
            if time.monotonic() < self._lamp_write_until and self.data is not None:
                # Keep the optimistic value while the firmware fades.
                lamp = self.data.lamp
            settings = await self.device.settings()

            now = time.monotonic()
            if self._last_slow == 0 or now - self._last_slow >= self.slow_poll_interval:
                self._alarms = tuple(await self.device.alarms())
                self._alarm_count = await self.device.alarm_count()
                self._alarm_enabled = await self.device.alarm_enabled()
                self._programs = {}
                self._program_infos = {}
                for program_type in PROGRAM_TYPES:
                    self._programs[program_type] = await self.device.program_settings(program_type)
                    self._program_infos[program_type] = await self.device.program_info(program_type)
                self._last_slow = now

            return AuraSnapshot(
                probe=self._probe,
                status=status,
                lamp=lamp,
                settings=settings,
                alarm_enabled=self._alarm_enabled,
                alarms=self._alarms,
                alarm_count=self._alarm_count,
                programs=self._programs,
                program_infos=self._program_infos,
                last_seen=time.time(),
            )
        except ProbeChallengeError as err:
            raise UpdateFailed(
                "The Aura requires the Withings association secret; local control is not available"
            ) from err
        except AuraError as err:
            raise UpdateFailed(str(err)) from err

    async def _async_write(self, coro, *, optimistic: AuraSnapshot | None = None) -> None:
        try:
            await coro
        except AuraError as err:
            await self.async_request_refresh()
            raise HomeAssistantError(f"Withings Aura command failed: {err}") from err
        if optimistic is not None:
            self.async_set_updated_data(optimistic)
        self.hass.async_create_task(self._async_delayed_refresh())

    async def _async_delayed_refresh(self) -> None:
        await asyncio.sleep(3.0)
        try:
            await self.async_request_refresh()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Delayed Aura refresh failed", exc_info=True)

    def _snapshot_with(self, **changes: Any) -> AuraSnapshot | None:
        if self.data is None:
            return None
        return replace(self.data, **changes, last_seen=time.time())

    def async_update_lamp(self, red: int, green: int, blue: int, on: bool) -> None:
        """Apply an optimistic lamp state for responsive UI."""
        optimistic = self._snapshot_with(
            lamp=LampState(red=red, green=green, blue=blue, state=1 if on else 0)
        )
        if optimistic is not None:
            self.async_set_updated_data(optimistic)

    async def async_set_lamp(self, red: int, green: int, blue: int, on: bool) -> None:
        optimistic = self._snapshot_with(
            lamp=LampState(red=red, green=green, blue=blue, state=1 if on else 0)
        )
        self._lamp_write_until = time.monotonic() + 5.0
        try:
            await self._async_write(
                self.device.set_lamp(red, green, blue, on),
                optimistic=optimistic,
            )
        except Exception:
            self._lamp_write_until = 0.0
            raise

    async def async_set_clock_display(self, on: bool, brightness: int) -> None:
        settings = self.data.settings if self.data else AuraSettings()
        optimistic = self._snapshot_with(
            settings=replace(settings, clock_display=on, clock_brightness=brightness)
        )
        await self._async_write(
            self.device.set_clock_display(on, brightness),
            optimistic=optimistic,
        )

    async def async_set_private_mode(self, on: bool) -> None:
        settings = self.data.settings if self.data else AuraSettings()
        optimistic = self._snapshot_with(settings=replace(settings, private_mode=on))
        await self._async_write(self.device.set_private_mode(on), optimistic=optimistic)

    async def async_set_alarm_enabled(self, on: bool) -> None:
        optimistic = self._snapshot_with(alarm_enabled=on)
        await self._async_write(self.device.set_alarm_enabled(on), optimistic=optimistic)

    async def async_start_program(
        self,
        program_type: int,
        program_id: int | None = None,
        volume: int | None = None,
        brightness: int | None = None,
        web_radio: str | None = None,
    ) -> None:
        await self._async_write(
            self.device.start_program(program_type, program_id, volume, brightness, web_radio)
        )

    async def async_stop_program(self) -> None:
        await self._async_write(self.device.stop_program())

    async def async_snooze(self) -> None:
        await self._async_write(self.device.snooze())

    async def async_sync_time(self, twelve_hour: bool | None = None) -> None:
        now = dt_util.now()
        info = time_sync_info(now)
        await self._async_write(self.device.sync_time(now, twelve_hour))
        self.time_sync = info
        self.async_update_listeners()

    async def async_set_program_settings(
        self,
        program_type: int,
        volume: int | None = None,
        brightness: int | None = None,
        program_id: int | None = None,
    ) -> None:
        self._last_slow = 0
        await self._async_write(
            self.device.set_program_settings(program_type, volume, brightness, program_id)
        )

    async def async_set_alarm(
        self,
        slot: int,
        hour: int,
        minute: int,
        days: list[str],
        enabled: bool,
        program_id: int,
        one_shot_date: str | None = None,
        volume: int | None = None,
        brightness: int | None = None,
        setting_id: int | None = None,
        web_radio: str | None = None,
    ) -> None:
        self._last_slow = 0
        await self._async_write(
            self.device.set_alarm(
                slot,
                hour,
                minute,
                days,
                enabled,
                program_id,
                one_shot_date,
                volume,
                brightness,
                setting_id,
                web_radio,
            )
        )
