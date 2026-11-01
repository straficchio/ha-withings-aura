"""Typed WPP device API for the Withings Aura."""

from __future__ import annotations

import asyncio
from datetime import datetime

from .const import (
    CMD_GET_ALARM_ENABLED,
    CMD_GET_ALARMS,
    CMD_GET_LAMP,
    CMD_GET_NB_ALARM,
    CMD_GET_PROGRAM_INFO,
    CMD_GET_PROGRAM_SETTINGS,
    CMD_GET_SETTINGS,
    CMD_GET_STATUS,
    CMD_PROBE,
    CMD_SET_ALARM,
    CMD_SET_ALARM_ENABLED,
    CMD_SET_CLOCK_MODE,
    CMD_SET_LAMP,
    CMD_SET_PROGRAM_SETTINGS,
    CMD_SET_SETTINGS,
    CMD_SNOOZE,
    CMD_START_PROGRAM,
    CMD_STOP_PROGRAM,
    CMD_TIME_SET,
    PROGRAM_TYPE_NAMES,
    TLV_PROBE_REPLY,
)
from .exceptions import AuraTimeoutError
from .models import Alarm, AuraSettings, AuraStatus, LampState, ProbeInfo, ProgramInfo
from .protocol import (
    AuraProtocolError,
    ProbeChallengeError,
    build_clock_mode,
    build_get_program_info,
    build_get_program_settings,
    build_set_alarm,
    build_set_alarm_enabled,
    build_set_clock_display,
    build_set_lamp,
    build_set_private_mode,
    build_set_program_settings,
    build_start_program,
    build_time_set,
    decode_alarm_count,
    decode_alarm_enabled,
    decode_alarms,
    decode_lamp,
    decode_probe,
    decode_program_info,
    decode_program_settings,
    decode_settings,
    decode_status,
    decode_tlvs,
)
from .transport import AuraBridge


class AuraDevice:
    """High-level typed API on top of :class:`AuraBridge`."""

    def __init__(self, bridge: AuraBridge) -> None:
        self.bridge = bridge

    async def probe(self) -> ProbeInfo:
        """Read the device identity, raising if the unit wants a challenge."""
        command, body = await self.bridge.async_request(CMD_PROBE, expect=(CMD_PROBE, 296))
        if command == 296:
            raise ProbeChallengeError("unit requires the association secret (ProbeChallenge)")
        for tlv_type, _value in decode_tlvs(body):
            if tlv_type == TLV_PROBE_REPLY:
                return decode_probe(body)
        raise AuraProtocolError("probe reply missing ProbeReply")

    async def status(self) -> AuraStatus:
        _command, body = await self.bridge.async_request(CMD_GET_STATUS)
        return decode_status(body)

    async def lamp(self) -> LampState:
        _command, body = await self.bridge.async_request(CMD_GET_LAMP)
        return decode_lamp(body)

    async def settings(self) -> AuraSettings:
        _command, body = await self.bridge.async_request(CMD_GET_SETTINGS)
        return decode_settings(body)

    async def alarms(self) -> list[Alarm]:
        _command, body = await self.bridge.async_request(CMD_GET_ALARMS)
        return decode_alarms(body)

    async def alarm_count(self) -> int | None:
        _command, body = await self.bridge.async_request(CMD_GET_NB_ALARM)
        return decode_alarm_count(body)

    async def alarm_enabled(self) -> bool | None:
        _command, body = await self.bridge.async_request(CMD_GET_ALARM_ENABLED)
        return decode_alarm_enabled(body)

    async def program_settings(self, program_type: int, program_id: int = 0) -> dict[str, str]:
        _command, body = await self.bridge.async_request(
            CMD_GET_PROGRAM_SETTINGS, build_get_program_settings(program_type, program_id)
        )
        return decode_program_settings(body)

    async def program_info(self, program_type: int, program_id: int = 0) -> ProgramInfo | None:
        _command, body = await self.bridge.async_request(
            CMD_GET_PROGRAM_INFO, build_get_program_info(program_type, program_id)
        )
        return decode_program_info(body)

    async def set_lamp(self, red: int, green: int, blue: int, on: bool) -> None:
        body = build_set_lamp(red, green, blue, on)
        for attempt in range(2):
            try:
                await self.bridge.async_request(CMD_SET_LAMP, body)
                return
            except AuraTimeoutError:
                if attempt == 1:
                    raise
                await asyncio.sleep(0.5)

    async def set_clock_display(self, on: bool, brightness: int) -> None:
        await self.bridge.async_request(CMD_SET_SETTINGS, build_set_clock_display(on, brightness))

    async def set_private_mode(self, on: bool) -> None:
        await self.bridge.async_request(CMD_SET_SETTINGS, build_set_private_mode(on))

    async def set_alarm_enabled(self, on: bool) -> None:
        await self.bridge.async_request(CMD_SET_ALARM_ENABLED, build_set_alarm_enabled(on))

    async def start_program(
        self,
        program_type: int,
        program_id: int | None = None,
        volume: int | None = None,
        brightness: int | None = None,
        web_radio: str | None = None,
    ) -> None:
        await self.bridge.async_request(
            CMD_START_PROGRAM,
            build_start_program(program_type, program_id, volume, brightness, web_radio),
        )

    async def stop_program(self) -> None:
        await self.bridge.async_request(CMD_STOP_PROGRAM)

    async def snooze(self) -> None:
        await self.bridge.async_request(CMD_SNOOZE)

    async def set_program_settings(
        self,
        program_type: int,
        volume: int | None = None,
        brightness: int | None = None,
        program_id: int | None = None,
    ) -> None:
        await self.bridge.async_request(
            CMD_SET_PROGRAM_SETTINGS,
            build_set_program_settings(program_type, volume, brightness, program_id),
        )

    async def set_alarm(
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
        await self.bridge.async_request(
            CMD_SET_ALARM,
            build_set_alarm(
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
            ),
        )

    async def sync_time(self, now: datetime, twelve_hour: bool | None = None) -> None:
        await self.bridge.async_request(CMD_TIME_SET, build_time_set(now))
        if twelve_hour is not None:
            await self.bridge.async_request(CMD_SET_CLOCK_MODE, build_clock_mode(twelve_hour))

    def program_name(self, program_type: int) -> str:
        return PROGRAM_TYPE_NAMES.get(program_type, str(program_type))
