"""Transport and device API tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.withings_aura.const import (
    CMD_SET_ALARM,
    CMD_SET_LAMP,
    CMD_SET_SETTINGS,
    CMD_START_PROGRAM,
    CMD_STOP_PROGRAM,
    CMD_TIME_SET,
)
from custom_components.withings_aura.device import AuraDevice
from custom_components.withings_aura.protocol import (
    ProbeChallengeError,
    build_set_alarm,
    build_set_lamp,
    decode_tlvs,
    tlv,
)
from custom_components.withings_aura.transport import AuraBridge


async def test_probe_and_reads(fake_bridge) -> None:
    bridge = AuraBridge(fake_bridge.host, fake_bridge.port)
    await bridge.async_connect()
    device = AuraDevice(bridge)

    probe = await device.probe()
    assert probe.name == "WSD"
    assert probe.mac == "00:11:22:33:44:55"
    assert probe.firmware == 1301
    assert probe.hardware == 12

    status = await device.status()
    assert status.status == 0
    assert status.substatus == 0

    lamp = await device.lamp()
    assert lamp.is_on is False
    assert lamp.brightness == 0

    settings = await device.settings()
    assert settings.clock_display is True
    assert settings.clock_brightness == 55
    assert settings.private_mode is False

    alarms = await device.alarms()
    assert len(alarms) == 2
    assert alarms[0].time == "06:45"
    assert alarms[0].program_id == 15

    assert await device.alarm_count() == 10
    assert await device.alarm_enabled() is False
    assert (await device.program_settings(1))["1"] == "50"
    info = await device.program_info(2)
    assert info is not None
    assert info.program_id == 1

    await bridge.async_close()


async def test_writes(fake_bridge) -> None:
    bridge = AuraBridge(fake_bridge.host, fake_bridge.port)
    await bridge.async_connect()
    device = AuraDevice(bridge)

    await device.set_lamp(0x1999, 0x0CCC, 0x0666, True)
    assert fake_bridge.last_request(CMD_SET_LAMP) == build_set_lamp(0x1999, 0x0CCC, 0x0666, True)

    await device.set_clock_display(False, 42)
    assert fake_bridge.last_request(CMD_SET_SETTINGS) == tlv(2317, bytes([0, 42]))

    await device.set_private_mode(True)
    assert fake_bridge.last_request(CMD_SET_SETTINGS) == tlv(2059, b"\x00")

    await device.set_alarm_enabled(True)
    assert fake_bridge.last_request(2331) == tlv(2329, b"\x01")

    await device.start_program(2, 1, 50, 97)
    body = fake_bridge.last_request(CMD_START_PROGRAM)
    assert body is not None
    assert decode_tlvs(body)[0] == (2312, b"\x02\x01")

    await device.stop_program()
    assert fake_bridge.last_request(CMD_STOP_PROGRAM) == b""

    await device.snooze()
    assert fake_bridge.last_request(2321) == b""

    await device.set_alarm(
        slot=1,
        hour=6,
        minute=45,
        days=["mon", "tue", "wed", "thu", "fri"],
        enabled=True,
        program_id=15,
        volume=46,
        brightness=50,
        setting_id=1,
    )
    assert fake_bridge.last_request(CMD_SET_ALARM) == build_set_alarm(
        slot=1,
        hour=6,
        minute=45,
        days=["mon", "tue", "wed", "thu", "fri"],
        enabled=True,
        program_id=15,
        volume=46,
        brightness=50,
        setting_id=1,
    )

    await device.sync_time(datetime(2026, 10, 31, 12, 0, tzinfo=UTC), True)
    assert fake_bridge.last_request(CMD_TIME_SET) is not None
    assert fake_bridge.last_request(2314) == tlv(2314, b"\x01")

    await bridge.async_close()


async def test_probe_challenge(fake_bridge) -> None:
    fake_bridge.responses[257] = tlv(290, b"\x00" + b"\x00")
    fake_bridge.response_commands[257] = 296
    bridge = AuraBridge(fake_bridge.host, fake_bridge.port)
    await bridge.async_connect()
    device = AuraDevice(bridge)
    with pytest.raises(ProbeChallengeError):
        await device.probe()
    await bridge.async_close()


async def test_reconnect(fake_bridge) -> None:
    bridge = AuraBridge(fake_bridge.host, fake_bridge.port)
    await bridge.async_connect()
    device = AuraDevice(bridge)
    assert (await device.probe()).firmware == 1301
    await bridge.async_close()
    await bridge.async_connect()
    assert (await device.status()).status == 0
    await bridge.async_close()
