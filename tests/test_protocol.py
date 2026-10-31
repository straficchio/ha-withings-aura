"""Protocol tests for the Withings Aura integration."""

from __future__ import annotations

import struct

from custom_components.withings_aura.const import (
    ALARM_ENABLED_BIT,
    TLV_PROGRAM_SETTING,
    TLV_SET_ALARM,
)
from custom_components.withings_aura.protocol import (
    build_set_alarm,
    build_set_lamp,
    decode_alarms,
    decode_lamp,
    decode_probe,
    decode_settings,
    decode_status,
    decode_tlvs,
    encode_request,
    extract_frag_frames,
    lamp_channels,
    list_to_days_mask,
    tlv,
)

PROBE_RESPONSE = bytes.fromhex(
    "0101004a"
    "0101010045"
    "01010041"
    "00000000"
    "03575344"
    "1130303a31313a32323a33333a34343a3535"
    "1030303131323233333434353536363737"
    "0000000c"
    "053930303035"
    "ffffffff"
    "00000515"
    "ffffffff"
)

STATUS_BODY = bytes.fromhex("0907000100090f000100091d000400000000")

LAMP_BODY = bytes.fromhex("09140006000000000000090c000100")

SETTINGS_BODY = bytes.fromhex("090d00020137080b000101")

ALARMS_BODY = bytes.fromhex(
    "05120007062d3e0000000f"
    "0916000401023436"
    "0916001602143138343436373434303733373039353531363135"
    "09160003030131"
    "0512000707003e00000014"
    "0916001601143138343436373434303733373039353531363135"
    "0916001602143138343436373434303733373039353531363135"
    "09160003030131"
)


def test_encode_probe_request() -> None:
    assert encode_request(257).hex() == "0009010100050101010000"


def test_extract_and_decode_probe() -> None:
    buffer = bytearray(PROBE_RESPONSE)
    payloads = extract_frag_frames(buffer)
    assert not buffer
    assert len(payloads) == 1
    assert payloads[0].startswith(bytes.fromhex("0101010045"))

    # Strip the WPP header and decode the ProbeReply TLV.
    body = payloads[0][5:]
    probe = decode_probe(body)
    assert probe.name == "WSD"
    assert probe.mac == "00:11:22:33:44:55"
    assert probe.firmware == 1301
    assert probe.hardware == 12
    assert probe.mfg_id == "90005"
    assert probe.secret == "0011223344556677"


def test_decode_status() -> None:
    status = decode_status(STATUS_BODY)
    assert status.status == 0
    assert status.substatus == 0
    assert status.extra == b"\x00\x00\x00\x00"
    assert not status.playing


def test_decode_lamp() -> None:
    lamp = decode_lamp(LAMP_BODY)
    assert lamp.red == lamp.green == lamp.blue == 0
    assert lamp.state == 0
    assert not lamp.is_on
    assert lamp.brightness == 0
    assert lamp.rgb == (0, 0, 0)


def test_decode_settings() -> None:
    settings = decode_settings(SETTINGS_BODY)
    assert settings.clock_display is True
    assert settings.clock_brightness == 55
    assert settings.private_mode is False


def test_decode_alarms() -> None:
    alarms = decode_alarms(ALARMS_BODY)
    assert len(alarms) == 2
    first, second = alarms
    assert first.time == "06:45"
    assert first.days == ["mon", "tue", "wed", "thu", "fri"]
    assert first.enabled is False
    assert first.program_id == 15
    assert first.volume == "46"
    assert first.brightness == "18446744073709551615"
    assert first.setting_id == "1"
    assert second.time == "07:00"
    assert second.program_id == 20


def test_lamp_channels() -> None:
    assert lamp_channels((255, 255, 255), 100) == (65535, 65535, 65535)
    assert lamp_channels((255, 0, 0), 50) == (32768, 0, 0)
    assert lamp_channels((0, 0, 0), 100) == (0, 0, 0)


def test_build_set_lamp() -> None:
    body = build_set_lamp(0x1999, 0x0CCC, 0x0666, True)
    tlvs = decode_tlvs(body)
    assert tlvs[0][0] == 2324
    assert struct.unpack(">HHH", tlvs[0][1]) == (0x1999, 0x0CCC, 0x0666)
    assert tlvs[1] == (2316, b"\x01")


def test_build_set_alarm() -> None:
    body = build_set_alarm(
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
    tlvs = decode_tlvs(body)
    assert tlvs[0] == (294, b"\x01")
    assert tlvs[1][0] == TLV_SET_ALARM
    hour, minute, mask, day, month, year, program = struct.unpack(">BBBBBBB", tlvs[1][1])
    assert (hour, minute, day, month, year, program) == (6, 45, 0, 0, 0, 15)
    assert mask == list_to_days_mask(["mon", "tue", "wed", "thu", "fri"]) | ALARM_ENABLED_BIT
    settings = {value[0]: value for _, value in tlvs if _ == TLV_PROGRAM_SETTING}
    assert settings[1] == b"\x01\x02" + b"46"
    assert settings[2] == b"\x02\x02" + b"50"
    assert settings[3] == b"\x03\x01" + b"1"


def test_tlv_roundtrip() -> None:
    encoded = tlv(0x1234, b"abc")
    assert decode_tlvs(encoded) == [(0x1234, b"abc")]
