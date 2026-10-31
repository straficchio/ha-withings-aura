"""Constants for the Withings Aura integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import CONF_HOST as CONF_HOST
from homeassistant.const import CONF_PORT as CONF_PORT

DOMAIN = "withings_aura"
MANUFACTURER = "Withings"
MODEL = "Aura (WSD01)"
DEFAULT_NAME = "Withings Aura"
DEFAULT_PORT = 7685
DEFAULT_POLL_INTERVAL = 30
DEFAULT_SLOW_POLL_INTERVAL = 300
MIN_POLL_INTERVAL = 10
MAX_POLL_INTERVAL = 300
MIN_SLOW_POLL_INTERVAL = 60
MAX_SLOW_POLL_INTERVAL = 3600
ZEROCONF_TYPE = "_withings-aura-bridge._tcp.local."

CONF_MAC = "mac"
CONF_FIRMWARE = "firmware"
CONF_POLL_INTERVAL = "poll_interval"
CONF_SLOW_POLL_INTERVAL = "slow_poll_interval"
CONF_ENTRY_ID = "entry_id"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=DEFAULT_POLL_INTERVAL)
DEFAULT_SLOW_INTERVAL = timedelta(seconds=DEFAULT_SLOW_POLL_INTERVAL)

# WPP commands
CMD_PROBE = 257
CMD_DISCONNECT = 272
CMD_TIME_SET = 1281
CMD_GET_ALARMS = 293
CMD_SET_ALARM = 297
CMD_GET_NB_ALARM = 298
CMD_GET_STATUS = 2311
CMD_GET_LAMP = 2318
CMD_SET_LAMP = 2317
CMD_GET_SETTINGS = 2320
CMD_SET_SETTINGS = 2319
CMD_GET_PROGRAM_SETTINGS = 2310
CMD_SET_PROGRAM_SETTINGS = 2309
CMD_GET_PROGRAM_INFO = 2313
CMD_START_PROGRAM = 2312
CMD_SELECT_PROGRAM = 2307
CMD_STOP_PROGRAM = 2308
CMD_SNOOZE = 2321
CMD_SET_CLOCK_MODE = 2314
CMD_GET_ALARM_ENABLED = 2330
CMD_SET_ALARM_ENABLED = 2331

# WPP TLV types
TLV_NULL = 256
TLV_PROBE_REPLY = 257
TLV_TIME_SET = 1281
TLV_TIME_SET_REPLY = 1282
TLV_ALARM_ID = 294
TLV_NB_ALARM = 295
TLV_SET_ALARM = 1298
TLV_PRIVATE_MODE = 2059
TLV_STATUS = 2311
TLV_PROGRAM_ID = 2312
TLV_PROGRAM_INFO = 2313
TLV_CLOCK_MODE = 2314
TLV_COLOR = 2315
TLV_LAMP_STATE = 2316
TLV_CLOCK_DISPLAY = 2317
TLV_SUBSTATUS = 2319
TLV_LAMP_RGB = 2324
TLV_PROGRAM_SETTING = 2326
TLV_PROGRAM_TYPE = 2327
TLV_RETURN_CODE = 2328
TLV_ALARM_ENABLED = 2329
TLV_STATUS_EXTRA = 2333

# Status enums
STATUS_NAMES = {
    0: "idle",
    1: "sleep",
    2: "wake_up",
    3: "nap",
    4: "mood",
    5: "demo",
    6: "media",
    7: "lullaby",
    255: "invalid",
}
STATUS_LABELS = {
    0: "Idle",
    1: "Sleep",
    2: "Wake-up",
    3: "Nap",
    4: "Mood",
    5: "Demo",
    6: "Media",
    7: "Lullaby",
    255: "Invalid",
}
SUBSTATUS_NAMES = {0: "idle", 1: "playing", 2: "paused", 3: "invalid"}

# Program types
PROGRAM_TYPES = {1: "mood", 2: "nap", 3: "sleep", 4: "wake_up", 5: "retail", 6: "media"}
PROGRAM_TYPE_NAMES = {1: "Mood", 2: "Nap", 3: "Sleep", 4: "Wake-up", 5: "Retail", 6: "Media"}
PROGRAM_NAME_TO_TYPE = {v: k for k, v in PROGRAM_TYPES.items()}
PROGRAM_OPTIONS = list(PROGRAM_TYPES.values())
DEFAULT_PROGRAM_IDS = {1: 0, 2: 1, 3: 1, 4: 1, 5: 0, 6: 0}

# Program setting keys
PROGRAM_SETTING_VOLUME = 1
PROGRAM_SETTING_BRIGHTNESS = 2
PROGRAM_SETTING_ID = 3
PROGRAM_SETTING_WEB_RADIO = 4
PROGRAM_SETTING_WEB_RADIO_NAME = 8
PROGRAM_SETTING_SPOTIFY_TAG = 6
PROGRAM_SETTING_SPOTIFY_NAME = 7

# Alarm days
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_LABELS = {
    "mon": "Mon",
    "tue": "Tue",
    "wed": "Wed",
    "thu": "Thu",
    "fri": "Fri",
    "sat": "Sat",
    "sun": "Sun",
}
ALARM_ENABLED_BIT = 0x80
