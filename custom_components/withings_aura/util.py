"""Small helpers for the Withings Aura integration."""

from __future__ import annotations

import re

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
