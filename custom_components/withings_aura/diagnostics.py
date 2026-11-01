"""Diagnostics for the Withings Aura integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .runtime import AuraConfigEntry

TO_REDACT = {"secret"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AuraConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data
    payload: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "unique_id": entry.unique_id,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "last_update_success": coordinator.last_update_success,
        "selected_program": coordinator.selected_program,
        "time_sync": coordinator.time_sync,
    }
    if data is not None:
        payload.update(
            {
                "probe": async_redact_data(asdict(data.probe), TO_REDACT),
                "status": asdict(data.status),
                "lamp": {
                    **asdict(data.lamp),
                    "is_on": data.lamp.is_on,
                    "brightness": data.lamp.brightness,
                    "rgb": data.lamp.rgb,
                },
                "settings": asdict(data.settings),
                "alarm_enabled": data.alarm_enabled,
                "alarm_count": data.alarm_count,
                "alarms": [alarm.as_dict() for alarm in data.alarms],
                "programs": data.programs,
                "program_infos": {
                    str(key): asdict(value) if value is not None else None
                    for key, value in data.program_infos.items()
                },
                "last_seen": data.last_seen,
            }
        )
    return payload
