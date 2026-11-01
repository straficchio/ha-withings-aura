"""Alarm helpers shared by the time and switch platforms."""

from __future__ import annotations

from .coordinator import AuraCoordinator
from .models import Alarm
from .util import parse_optional_int

DEFAULT_ALARM_DAYS = ["mon", "tue", "wed", "thu", "fri"]
DEFAULT_ALARM_PROGRAM = 15
DEFAULT_ALARM_HOUR = 7
DEFAULT_ALARM_MINUTE = 0


async def async_save_alarm(
    coordinator: AuraCoordinator,
    slot: int,
    alarm: Alarm | None,
    *,
    hour: int | None = None,
    minute: int | None = None,
    enabled: bool | None = None,
) -> None:
    """Create or update an alarm, preserving fields not being changed."""
    await coordinator.async_set_alarm(
        slot=slot,
        hour=alarm.hour
        if hour is None and alarm
        else (hour if hour is not None else DEFAULT_ALARM_HOUR),
        minute=(
            alarm.minute
            if minute is None and alarm
            else (minute if minute is not None else DEFAULT_ALARM_MINUTE)
        ),
        days=alarm.days if alarm and alarm.days else DEFAULT_ALARM_DAYS,
        enabled=(alarm.enabled if alarm else True) if enabled is None else enabled,
        program_id=alarm.program_id if alarm else DEFAULT_ALARM_PROGRAM,
        one_shot_date=alarm.one_shot_date if alarm else None,
        volume=parse_optional_int(alarm.volume) if alarm else None,
        brightness=parse_optional_int(alarm.brightness) if alarm else None,
        setting_id=parse_optional_int(alarm.setting_id) if alarm else None,
        web_radio=alarm.web_radio if alarm else None,
    )
