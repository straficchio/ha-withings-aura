"""Services for the Withings Aura integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ENTRY_ID,
    DAYS,
    DOMAIN,
    PROGRAM_NAME_TO_TYPE,
    PROGRAM_OPTIONS,
)
from .runtime import AuraConfigEntry
from .util import parse_hhmm

_LOGGER = logging.getLogger(__name__)

SERVICE_START_PROGRAM = "start_program"
SERVICE_STOP_PROGRAM = "stop_program"
SERVICE_SNOOZE = "snooze"
SERVICE_TRIGGER_ALARM = "trigger_alarm"
SERVICE_SET_ALARM = "set_alarm"
SERVICE_SET_ALARM_ENABLED = "set_alarm_enabled"
SERVICE_SET_CLOCK_DISPLAY = "set_clock_display"
SERVICE_SYNC_TIME = "sync_time"
SERVICE_SET_PROGRAM_SETTINGS = "set_program_settings"

ENTRY_SCHEMA = {vol.Optional(CONF_ENTRY_ID): cv.string}

START_PROGRAM_SCHEMA = vol.Schema(
    {
        **ENTRY_SCHEMA,
        vol.Required("program_type"): vol.In(PROGRAM_OPTIONS),
        vol.Optional("program_id"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        vol.Optional("volume"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("brightness"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("web_radio"): cv.string,
    }
)
STOP_PROGRAM_SCHEMA = vol.Schema({**ENTRY_SCHEMA})
SNOOZE_SCHEMA = vol.Schema({**ENTRY_SCHEMA})
TRIGGER_ALARM_SCHEMA = vol.Schema(
    {
        **ENTRY_SCHEMA,
        vol.Optional("program_id", default=15): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        vol.Optional("volume"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("brightness"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)
SET_ALARM_SCHEMA = vol.Schema(
    {
        **ENTRY_SCHEMA,
        vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
        vol.Required("time"): cv.string,
        vol.Optional("days", default=[]): vol.All(cv.ensure_list, [vol.In(DAYS)]),
        vol.Optional("program_id", default=15): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        vol.Optional("enabled", default=True): cv.boolean,
        vol.Optional("one_shot_date"): cv.string,
        vol.Optional("volume"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("brightness"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("setting_id"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        vol.Optional("web_radio"): cv.string,
    }
)
SET_ALARM_ENABLED_SCHEMA = vol.Schema({**ENTRY_SCHEMA, vol.Required("enabled"): cv.boolean})
SET_CLOCK_DISPLAY_SCHEMA = vol.Schema(
    {
        **ENTRY_SCHEMA,
        vol.Required("display"): cv.boolean,
        vol.Optional("brightness"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)
SYNC_TIME_SCHEMA = vol.Schema({**ENTRY_SCHEMA, vol.Optional("twelve_hour"): cv.boolean})
SET_PROGRAM_SETTINGS_SCHEMA = vol.Schema(
    {
        **ENTRY_SCHEMA,
        vol.Required("program_type"): vol.In(PROGRAM_OPTIONS),
        vol.Optional("volume"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("brightness"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional("program_id"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
    }
)


def _get_entry(hass: HomeAssistant, call: ServiceCall) -> AuraConfigEntry:
    entry_id = call.data.get(CONF_ENTRY_ID)
    if entry_id:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise HomeAssistantError(f"Unknown Withings Aura entry: {entry_id}")
        if entry.state is not ConfigEntryState.LOADED:
            raise HomeAssistantError("The selected Withings Aura entry is not loaded")
        return entry
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if len(entries) != 1:
        raise HomeAssistantError("Specify entry_id when more than one Withings Aura is configured")
    return entries[0]


async def _handle_start_program(call: ServiceCall) -> None:
    hass = call.hass
    entry = _get_entry(hass, call)
    program_type = PROGRAM_NAME_TO_TYPE[call.data["program_type"]]
    await entry.runtime_data.coordinator.async_start_program(
        program_type,
        call.data.get("program_id"),
        call.data.get("volume"),
        call.data.get("brightness"),
        call.data.get("web_radio"),
    )


async def _handle_stop_program(call: ServiceCall) -> None:
    hass = call.hass
    await _get_entry(hass, call).runtime_data.coordinator.async_stop_program()


async def _handle_snooze(call: ServiceCall) -> None:
    hass = call.hass
    await _get_entry(hass, call).runtime_data.coordinator.async_snooze()


async def _handle_trigger_alarm(call: ServiceCall) -> None:
    hass = call.hass
    entry = _get_entry(hass, call)
    await entry.runtime_data.coordinator.async_start_program(
        4,
        call.data.get("program_id", 15),
        call.data.get("volume"),
        call.data.get("brightness"),
    )


async def _handle_set_alarm(call: ServiceCall) -> None:
    hass = call.hass
    entry = _get_entry(hass, call)
    hour, minute = parse_hhmm(call.data["time"])
    await entry.runtime_data.coordinator.async_set_alarm(
        slot=call.data["slot"],
        hour=hour,
        minute=minute,
        days=call.data["days"],
        enabled=call.data["enabled"],
        program_id=call.data["program_id"],
        one_shot_date=call.data.get("one_shot_date"),
        volume=call.data.get("volume"),
        brightness=call.data.get("brightness"),
        setting_id=call.data.get("setting_id"),
        web_radio=call.data.get("web_radio"),
    )


async def _handle_set_alarm_enabled(call: ServiceCall) -> None:
    hass = call.hass
    await _get_entry(hass, call).runtime_data.coordinator.async_set_alarm_enabled(
        call.data["enabled"]
    )


async def _handle_set_clock_display(call: ServiceCall) -> None:
    hass = call.hass
    entry = _get_entry(hass, call)
    brightness = call.data.get("brightness")
    if brightness is None:
        brightness = entry.runtime_data.coordinator.data.settings.clock_brightness
    await entry.runtime_data.coordinator.async_set_clock_display(call.data["display"], brightness)


async def _handle_sync_time(call: ServiceCall) -> None:
    hass = call.hass
    await _get_entry(hass, call).runtime_data.coordinator.async_sync_time(
        call.data.get("twelve_hour")
    )


async def _handle_set_program_settings(call: ServiceCall) -> None:
    hass = call.hass
    entry = _get_entry(hass, call)
    await entry.runtime_data.coordinator.async_set_program_settings(
        PROGRAM_NAME_TO_TYPE[call.data["program_type"]],
        call.data.get("volume"),
        call.data.get("brightness"),
        call.data.get("program_id"),
    )


def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get("services_registered"):
        return
    hass.services.async_register(
        DOMAIN, SERVICE_START_PROGRAM, _handle_start_program, schema=START_PROGRAM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_PROGRAM, _handle_stop_program, schema=STOP_PROGRAM_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_SNOOZE, _handle_snooze, schema=SNOOZE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_TRIGGER_ALARM, _handle_trigger_alarm, schema=TRIGGER_ALARM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_ALARM, _handle_set_alarm, schema=SET_ALARM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ALARM_ENABLED,
        _handle_set_alarm_enabled,
        schema=SET_ALARM_ENABLED_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CLOCK_DISPLAY,
        _handle_set_clock_display,
        schema=SET_CLOCK_DISPLAY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SYNC_TIME, _handle_sync_time, schema=SYNC_TIME_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PROGRAM_SETTINGS,
        _handle_set_program_settings,
        schema=SET_PROGRAM_SETTINGS_SCHEMA,
    )
    data["services_registered"] = True
