"""Small helpers for the Withings Aura integration."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import voluptuous as vol

_HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def normalize_mac(mac: str) -> str:
    """Normalize a MAC address to lowercase colon-separated form."""
    return mac.strip().lower().replace("-", ":")


def parse_hhmm(value: str) -> tuple[int, int]:
    """Parse HH:MM into hour/minute."""
    match = _HHMM.match(value.strip())
    if not match:
        raise vol.Invalid("time must be HH:MM")
    return int(match.group(1)), int(match.group(2))


def _offset_seconds(value: datetime) -> int:
    offset = value.utcoffset()
    return int(offset.total_seconds()) if offset is not None else 0


def parse_optional_int(value: str | None) -> int | None:
    """Parse an Aura string setting that may be unset (u64 max)."""
    if value in (None, "", "18446744073709551615"):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def format_offset(seconds: int) -> str:
    """Format a UTC offset in seconds as +HH:MM."""
    sign = "+" if seconds >= 0 else "-"
    seconds = abs(seconds)
    return f"{sign}{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}"


def next_dst_transition(now: datetime) -> datetime | None:
    """Return the next UTC offset change for an aware datetime, if any."""
    if now.tzinfo is None:
        return None
    current = _offset_seconds(now)
    cursor = now
    step = timedelta(hours=6)
    # Six-hour steps for a year catch both DST changes without a tz database API.
    for _ in range(370 * 4):
        candidate = cursor + step
        if _offset_seconds(candidate) != current:
            low, high = cursor, candidate
            while high - low > timedelta(minutes=1):
                middle = low + (high - low) / 2
                if _offset_seconds(middle) == current:
                    low = middle
                else:
                    high = middle
            return high
        cursor = candidate
    return None


def time_sync_info(now: datetime) -> dict[str, object]:
    """Describe the time/offset data sent to the Aura."""
    transition = next_dst_transition(now)
    current_offset = _offset_seconds(now)
    next_offset = _offset_seconds(transition) if transition is not None else current_offset
    return {
        "timezone": str(now.tzinfo),
        "utc_offset": current_offset,
        "utc_offset_text": format_offset(current_offset),
        "next_change": transition.isoformat() if transition is not None else None,
        "next_offset": next_offset,
        "next_offset_text": format_offset(next_offset),
        "synced_at": now.isoformat(),
    }
