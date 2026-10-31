"""Data models for the Withings Aura integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import DAYS, STATUS_LABELS


@dataclass(frozen=True, slots=True)
class ProbeInfo:
    """Reply to the WPP PROBE command."""

    vid: int
    pid: int
    name: str
    mac: str
    secret: str
    hardware: int
    mfg_id: str
    bootloader: int
    firmware: int
    rescue: int

    @property
    def normalized_mac(self) -> str:
        """Return the MAC as lowercase colon-separated text."""
        return self.mac.strip().lower()


@dataclass(frozen=True, slots=True)
class AuraStatus:
    """Playback status."""

    status: int = 0
    substatus: int = 0
    extra: bytes = b""

    @property
    def name(self) -> str:
        return STATUS_LABELS.get(self.status, str(self.status))

    @property
    def playing(self) -> bool:
        return self.status not in (0, 255)


@dataclass(frozen=True, slots=True)
class LampState:
    """Mood-light colour and state."""

    red: int = 0
    green: int = 0
    blue: int = 0
    state: int | None = None

    @property
    def is_on(self) -> bool:
        # The state byte is unreliable after a colour write; colour 0 is off.
        return any((self.red, self.green, self.blue))

    @property
    def brightness(self) -> int:
        peak = max(self.red, self.green, self.blue)
        return round(peak / 65535 * 100)

    @property
    def rgb(self) -> tuple[int, int, int]:
        return (round(self.red / 257), round(self.green / 257), round(self.blue / 257))


@dataclass(frozen=True, slots=True)
class AuraSettings:
    """Clock display and private-mode settings."""

    clock_display: bool = True
    clock_brightness: int = 50
    private_mode: bool = False


@dataclass(frozen=True, slots=True)
class Alarm:
    """One configured alarm."""

    slot: int
    hour: int
    minute: int
    enabled: bool
    days_mask: int
    one_shot_date: str | None
    program_id: int
    volume: str | None = None
    brightness: str | None = None
    setting_id: str | None = None
    web_radio: str | None = None
    web_radio_name: str | None = None
    spotify_tag: str | None = None
    spotify_name: str | None = None

    @property
    def days(self) -> list[str]:
        return [DAYS[i - 1] for i in range(1, 8) if self.days_mask & (1 << i)]

    @property
    def time(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "slot": self.slot,
            "time": self.time,
            "enabled": self.enabled,
            "days": self.days,
            "one_shot_date": self.one_shot_date,
            "program_id": self.program_id,
            "volume": self.volume,
            "brightness": self.brightness,
            "setting_id": self.setting_id,
            "web_radio": self.web_radio,
            "web_radio_name": self.web_radio_name,
            "spotify_tag": self.spotify_tag,
            "spotify_name": self.spotify_name,
        }


@dataclass(frozen=True, slots=True)
class ProgramInfo:
    """Aura program information."""

    type: int
    program_id: int
    flag_c: int
    flag_d: int
    value_e: int


@dataclass(slots=True)
class AuraSnapshot:
    """One coordinator snapshot."""

    probe: ProbeInfo
    status: AuraStatus
    lamp: LampState
    settings: AuraSettings
    alarm_enabled: bool | None = None
    alarms: tuple[Alarm, ...] = ()
    alarm_count: int | None = None
    programs: dict[int, dict[str, str]] = field(default_factory=dict)
    program_infos: dict[int, ProgramInfo | None] = field(default_factory=dict)
    last_seen: float = 0.0
