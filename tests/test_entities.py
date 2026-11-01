"""Entity and service tests for the Withings Aura integration."""

from __future__ import annotations

from datetime import time as dt_time
from datetime import timedelta

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_RGB_COLOR
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.withings_aura import async_setup
from custom_components.withings_aura.const import (
    CMD_SET_ALARM,
    CMD_SET_ALARM_ENABLED,
    CMD_SET_LAMP,
    CMD_SET_PROGRAM_SETTINGS,
    CMD_SET_SETTINGS,
    CMD_SNOOZE,
    CMD_START_PROGRAM,
    CMD_STOP_PROGRAM,
    DOMAIN,
)
from custom_components.withings_aura.protocol import decode_tlvs

from .fake_bridge import PROGRAM_SETTINGS_SLEEP

ENTITY_ID = "00:11:22:33:44:55"


async def setup_aura(hass, entry) -> None:
    entry.add_to_hass(hass)
    await async_setup(hass, {})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def entity_id(hass, platform: str, key: str) -> str:
    registry = er.async_get(hass)
    unique_id = f"{ENTITY_ID}_{key}"
    for entry in registry.entities.values():
        if entry.domain == platform and entry.unique_id == unique_id:
            return entry.entity_id
    raise AssertionError(f"entity not found: {platform} {unique_id}")


async def test_entities_exist(hass, mock_entry) -> None:
    await setup_aura(hass, mock_entry)

    assert hass.states.get(entity_id(hass, "light", "lamp")).state == STATE_OFF
    assert hass.states.get(entity_id(hass, "switch", "clock_display")).state == STATE_ON
    assert hass.states.get(entity_id(hass, "switch", "private_mode")).state == STATE_OFF
    assert hass.states.get(entity_id(hass, "switch", "alarm_enabled")).state == STATE_OFF
    assert hass.states.get(entity_id(hass, "number", "clock_brightness")).state == "55"
    assert hass.states.get(entity_id(hass, "sensor", "status")).state == "Idle"
    assert hass.states.get(entity_id(hass, "sensor", "firmware")).state == "1301"
    assert hass.states.get(entity_id(hass, "sensor", "alarm_count")).state == "10"
    assert hass.states.get(entity_id(hass, "sensor", "alarms")).state == "2"
    assert hass.states.get(entity_id(hass, "binary_sensor", "playing")).state == STATE_OFF


async def test_light_turn_on_off(hass, mock_entry, fake_bridge) -> None:
    await setup_aura(hass, mock_entry)
    light_id = entity_id(hass, "light", "lamp")

    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: light_id, ATTR_RGB_COLOR: [255, 0, 0], ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()

    body = fake_bridge.last_request(CMD_SET_LAMP)
    assert body is not None
    tlvs = decode_tlvs(body)
    assert tlvs[0][0] == 2324
    assert tlvs[0][1] == b"\x80\x00\x00\x00\x00\x00"
    assert tlvs[1] == (2316, b"\x01")
    assert hass.states.get(light_id).attributes["brightness"] == 128

    await hass.services.async_call("light", "turn_off", {ATTR_ENTITY_ID: light_id}, blocking=True)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert fake_bridge.last_request(CMD_SET_LAMP) is not None


async def test_clock_display_and_brightness(hass, mock_entry, fake_bridge) -> None:
    await setup_aura(hass, mock_entry)

    await hass.services.async_call(
        "switch",
        "turn_off",
        {ATTR_ENTITY_ID: entity_id(hass, "switch", "clock_display")},
        blocking=True,
    )
    body = fake_bridge.last_request(CMD_SET_SETTINGS)
    assert body == b"\x09\x0d\x00\x02\x00\x37"

    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: entity_id(hass, "number", "clock_brightness"), "value": 42},
        blocking=True,
    )
    body = fake_bridge.last_request(CMD_SET_SETTINGS)
    assert body == b"\x09\x0d\x00\x02\x00\x2a"


async def test_private_mode_and_alarm_switch(hass, mock_entry, fake_bridge) -> None:
    await setup_aura(hass, mock_entry)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: entity_id(hass, "switch", "private_mode")},
        blocking=True,
    )
    assert fake_bridge.last_request(CMD_SET_SETTINGS) == b"\x08\x0b\x00\x01\x00"

    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: entity_id(hass, "switch", "alarm_enabled")},
        blocking=True,
    )
    assert fake_bridge.last_request(CMD_SET_ALARM_ENABLED) == b"\x09\x19\x00\x01\x01"


async def test_buttons(hass, mock_entry, fake_bridge) -> None:
    await setup_aura(hass, mock_entry)

    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: entity_id(hass, "button", "start_program")},
        blocking=True,
    )
    assert fake_bridge.last_request(CMD_START_PROGRAM) is not None

    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: entity_id(hass, "button", "trigger_alarm")},
        blocking=True,
    )
    body = fake_bridge.last_request(CMD_START_PROGRAM)
    assert body is not None
    assert decode_tlvs(body)[0] == (2312, b"\x04\x0f")

    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: entity_id(hass, "button", "stop_program")},
        blocking=True,
    )
    assert fake_bridge.last_request(CMD_STOP_PROGRAM) == b""

    await hass.services.async_call(
        "button", "press", {ATTR_ENTITY_ID: entity_id(hass, "button", "snooze")}, blocking=True
    )
    assert fake_bridge.last_request(CMD_SNOOZE) == b""


async def test_set_alarm_service(hass, mock_entry, fake_bridge) -> None:
    await setup_aura(hass, mock_entry)

    await hass.services.async_call(
        DOMAIN,
        "set_alarm",
        {
            "slot": 1,
            "time": "06:45",
            "days": ["mon", "tue", "wed", "thu", "fri"],
            "program_id": 15,
            "enabled": True,
            "volume": 46,
            "brightness": 50,
            "setting_id": 1,
        },
        blocking=True,
    )
    assert fake_bridge.last_request(CMD_SET_ALARM) is not None


async def test_trigger_alarm_service(hass, mock_entry, fake_bridge) -> None:
    await setup_aura(hass, mock_entry)

    await hass.services.async_call(
        DOMAIN,
        "trigger_alarm",
        {"program_id": 15, "volume": 50, "brightness": 50},
        blocking=True,
    )
    body = fake_bridge.last_request(CMD_START_PROGRAM)
    assert body is not None
    assert decode_tlvs(body)[0] == (2312, b"\x04\x0f")


async def test_program_select_and_start(hass, mock_entry, fake_bridge) -> None:
    await setup_aura(hass, mock_entry)
    select_id = entity_id(hass, "select", "program")
    assert hass.states.get(select_id).state == "mood"

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: select_id, "option": "sleep"},
        blocking=True,
    )
    assert hass.states.get(select_id).state == "sleep"

    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: entity_id(hass, "button", "start_program")},
        blocking=True,
    )
    body = fake_bridge.last_request(CMD_START_PROGRAM)
    assert body is not None
    assert decode_tlvs(body)[0] == (2312, b"\x03\x01")


async def test_program_volume(hass, mock_entry, fake_bridge) -> None:
    fake_bridge.program_settings[3] = PROGRAM_SETTINGS_SLEEP
    await setup_aura(hass, mock_entry)
    volume_id = entity_id(hass, "number", "program_volume")
    assert hass.states.get(volume_id).state == "50"

    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: volume_id, "value": 42},
        blocking=True,
    )
    body = fake_bridge.last_request(CMD_SET_PROGRAM_SETTINGS)
    assert body is not None
    tlvs = decode_tlvs(body)
    assert tlvs[0] == (2327, b"\x01\x00\x00\x00\x00")
    assert tlvs[1] == (2326, b"\x01\x0242")

    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id(hass, "select", "program"), "option": "sleep"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(volume_id).state == "29"


async def test_alarm_time_and_switch(hass, mock_entry, fake_bridge) -> None:
    await setup_aura(hass, mock_entry)

    time_id = entity_id(hass, "time", "alarm_1_time")
    assert hass.states.get(time_id).state == "06:45:00"

    await hass.services.async_call(
        "time",
        "set_value",
        {ATTR_ENTITY_ID: time_id, "time": dt_time(7, 30)},
        blocking=True,
    )
    body = fake_bridge.last_request(CMD_SET_ALARM)
    assert body is not None
    tlvs = decode_tlvs(body)
    alarm = dict(tlvs)[1298]
    hour, minute, mask, _day, _month, _year, program = alarm
    assert (hour, minute, program) == (7, 30, 15)
    assert mask == 0x3E  # Mon-Fri, disabled

    switch_id = entity_id(hass, "switch", "alarm_1_enabled")
    assert hass.states.get(switch_id).state == STATE_OFF
    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: switch_id},
        blocking=True,
    )
    body = fake_bridge.last_request(CMD_SET_ALARM)
    assert body is not None
    alarm = dict(decode_tlvs(body))[1298]
    assert alarm[2] & 0x80
