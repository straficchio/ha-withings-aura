"""WPP framing and codecs for the Withings Aura."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime

from .const import (
    ALARM_ENABLED_BIT,
    DAYS,
    DEFAULT_PROGRAM_IDS,
    PROGRAM_SETTING_BRIGHTNESS,
    PROGRAM_SETTING_ID,
    PROGRAM_SETTING_VOLUME,
    PROGRAM_SETTING_WEB_RADIO,
    TLV_ALARM_ENABLED,
    TLV_ALARM_ID,
    TLV_CLOCK_DISPLAY,
    TLV_CLOCK_MODE,
    TLV_COLOR,
    TLV_LAMP_RGB,
    TLV_LAMP_STATE,
    TLV_NB_ALARM,
    TLV_PRIVATE_MODE,
    TLV_PROBE_REPLY,
    TLV_PROGRAM_ID,
    TLV_PROGRAM_INFO,
    TLV_PROGRAM_SETTING,
    TLV_PROGRAM_TYPE,
    TLV_SET_ALARM,
    TLV_STATUS,
    TLV_STATUS_EXTRA,
    TLV_SUBSTATUS,
    TLV_TIME_SET,
)
from .models import Alarm, AuraSettings, AuraStatus, LampState, ProbeInfo, ProgramInfo
from .util import next_dst_transition


class AuraProtocolError(Exception):
    """Base protocol error."""


class ProbeChallengeError(AuraProtocolError):
    """The unit requires the association secret (ProbeChallenge)."""


@dataclass(frozen=True, slots=True)
class WppMessage:
    """A decoded WPP message."""

    command: int
    body: bytes


def tlv(tlv_type: int, value: bytes) -> bytes:
    """Encode one TLV."""
    return struct.pack(">HH", tlv_type, len(value)) + value


def wpp(command: int, body: bytes = b"") -> bytes:
    """Encode a WPP message."""
    return struct.pack(">BHH", 1, command, len(body)) + body


def frag(payload: bytes) -> bytes:
    """Encode a FragFsm data frame."""
    return struct.pack(">BBH", 1, 1, len(payload)) + payload


def encode_request(command: int, body: bytes = b"") -> bytes:
    """Encode a client request for the TCP bridge."""
    frame = frag(wpp(command, body))
    return struct.pack(">H", len(frame)) + frame


def decode_wpp(data: bytes) -> WppMessage:
    """Decode a WPP message."""
    if len(data) < 5:
        raise AuraProtocolError(f"short WPP message: {data.hex()}")
    version, command, length = struct.unpack(">BHH", data[:5])
    if version != 1:
        raise AuraProtocolError(f"unsupported WPP version {version}")
    if len(data) < 5 + length:
        raise AuraProtocolError(f"truncated WPP message: {data.hex()}")
    return WppMessage(command, data[5 : 5 + length])


def decode_tlvs(body: bytes) -> list[tuple[int, bytes]]:
    """Decode a TLV sequence."""
    result: list[tuple[int, bytes]] = []
    offset = 0
    while offset + 4 <= len(body):
        tlv_type, length = struct.unpack(">HH", body[offset : offset + 4])
        value = body[offset + 4 : offset + 4 + length]
        if len(value) != length:
            raise AuraProtocolError("truncated TLV")
        result.append((tlv_type, value))
        offset += 4 + length
    if offset != len(body):
        raise AuraProtocolError("trailing bytes after TLVs")
    return result


def extract_frag_frames(buffer: bytearray) -> list[bytes]:
    """Extract complete FragFsm payloads, mutating *buffer*."""
    payloads: list[bytes] = []
    while len(buffer) >= 4:
        proto, command, length = struct.unpack(">BBH", buffer[:4])
        if proto != 1:
            raise AuraProtocolError(f"unexpected FragFsm proto {proto}")
        if command == 0:  # reset
            del buffer[:4]
            continue
        if command != 1:
            raise AuraProtocolError(f"unexpected FragFsm command {command}")
        if len(buffer) < 4 + length:
            break
        payloads.append(bytes(buffer[4 : 4 + length]))
        del buffer[: 4 + length]
    return payloads


def _string(value: bytes, offset: int) -> tuple[str, int]:
    length = value[offset]
    offset += 1
    return value[offset : offset + length].decode("utf-8", "replace"), offset + length


def decode_probe_reply(value: bytes) -> ProbeInfo:
    """Decode the ProbeReply TLV."""
    offset = 0
    vid, pid = struct.unpack(">HH", value[offset : offset + 4])
    offset += 4
    name, offset = _string(value, offset)
    mac, offset = _string(value, offset)
    secret, offset = _string(value, offset)
    hardware = struct.unpack(">I", value[offset : offset + 4])[0]
    offset += 4
    mfg_id, offset = _string(value, offset)
    bootloader, firmware, rescue = struct.unpack(">III", value[offset : offset + 12])
    return ProbeInfo(
        vid=vid,
        pid=pid,
        name=name,
        mac=mac,
        secret=secret,
        hardware=hardware,
        mfg_id=mfg_id,
        bootloader=bootloader,
        firmware=firmware,
        rescue=rescue,
    )


def decode_probe(body: bytes) -> ProbeInfo:
    """Decode a PROBE reply body."""
    for tlv_type, value in decode_tlvs(body):
        if tlv_type == TLV_PROBE_REPLY:
            return decode_probe_reply(value)
    raise AuraProtocolError("probe reply did not contain a ProbeReply TLV")


def decode_status(body: bytes) -> AuraStatus:
    """Decode a GET_STATUS reply."""
    status = 0
    substatus = 0
    extra = b""
    for tlv_type, value in decode_tlvs(body):
        if tlv_type == TLV_STATUS and value:
            status = value[0]
        elif tlv_type == TLV_SUBSTATUS and value:
            substatus = value[0]
        elif tlv_type == TLV_STATUS_EXTRA:
            extra = value
    return AuraStatus(status=status, substatus=substatus, extra=extra)


def decode_lamp(body: bytes) -> LampState:
    """Decode a GET_LAMP reply."""
    red = green = blue = 0
    state: int | None = None
    for tlv_type, value in decode_tlvs(body):
        if tlv_type == TLV_LAMP_RGB and len(value) >= 6:
            red, green, blue = struct.unpack(">HHH", value[:6])
        elif tlv_type == TLV_COLOR and len(value) >= 8:
            red, green, blue, _ = struct.unpack(">HHHH", value[:8])
        elif tlv_type == TLV_LAMP_STATE and value:
            state = value[0]
    return LampState(red=red, green=green, blue=blue, state=state)


def decode_settings(body: bytes) -> AuraSettings:
    """Decode a GET_SETTINGS reply."""
    clock_display = True
    clock_brightness = 50
    private_mode = False
    for tlv_type, value in decode_tlvs(body):
        if tlv_type == TLV_CLOCK_DISPLAY and len(value) >= 2:
            clock_display = bool(value[0])
            clock_brightness = value[1]
        elif tlv_type == TLV_PRIVATE_MODE and value:
            private_mode = value[0] == 0
    return AuraSettings(
        clock_display=clock_display,
        clock_brightness=clock_brightness,
        private_mode=private_mode,
    )


def _program_setting_value(value: bytes) -> tuple[int, str]:
    key = value[0]
    length = value[1]
    return key, value[2 : 2 + length].decode("utf-8", "replace")


def decode_alarms(body: bytes) -> list[Alarm]:
    """Decode a GET_ALARMS reply into alarm objects."""
    alarms: list[Alarm] = []
    current: dict | None = None
    for tlv_type, value in decode_tlvs(body):
        if tlv_type == TLV_SET_ALARM and len(value) >= 7:
            hour, minute, days, day, month, year, program = struct.unpack(">BBBBBBB", value[:7])
            current = {
                "slot": len(alarms) + 1,
                "hour": hour,
                "minute": minute,
                "enabled": bool(days & ALARM_ENABLED_BIT),
                "days_mask": days & 0x7F,
                "one_shot_date": None if day == 0 else f"{year + 2000:04d}-{month:02d}-{day:02d}",
                "program_id": program,
            }
            alarms.append(Alarm(**current))
        elif tlv_type == TLV_PROGRAM_SETTING and len(value) >= 2 and alarms:
            key, text = _program_setting_value(value)
            current = current or {}
            current[key] = text
            # Replace the last alarm with the updated settings.
            base = alarms[-1]
            updates = {}
            if key == PROGRAM_SETTING_VOLUME:
                updates["volume"] = text
            elif key == PROGRAM_SETTING_BRIGHTNESS:
                updates["brightness"] = text
            elif key == PROGRAM_SETTING_ID:
                updates["setting_id"] = text
            elif key == 4:
                updates["web_radio"] = text
            elif key == 8:
                updates["web_radio_name"] = text
            elif key == 6:
                updates["spotify_tag"] = text
            elif key == 7:
                updates["spotify_name"] = text
            if updates:
                from dataclasses import replace

                alarms[-1] = replace(base, **updates)
    return alarms


def decode_alarm_count(body: bytes) -> int | None:
    """Decode GET_NB_ALARM."""
    for tlv_type, value in decode_tlvs(body):
        if tlv_type == TLV_NB_ALARM and value:
            return value[0]
    return None


def decode_alarm_enabled(body: bytes) -> bool | None:
    """Decode GET_ALARM_ENABLED."""
    for tlv_type, value in decode_tlvs(body):
        if tlv_type == TLV_ALARM_ENABLED and value:
            return bool(value[0])
    return None


def decode_program_settings(body: bytes) -> dict[str, str]:
    """Decode GET_PROGRAM_SETTINGS into key/value strings."""
    result: dict[str, str] = {}
    for tlv_type, value in decode_tlvs(body):
        if tlv_type == TLV_PROGRAM_SETTING and len(value) >= 2:
            key, text = _program_setting_value(value)
            result[str(key)] = text
    return result


def decode_program_info(body: bytes) -> ProgramInfo | None:
    """Decode GET_PROGRAM_INFO."""
    for tlv_type, value in decode_tlvs(body):
        if tlv_type == TLV_PROGRAM_INFO and len(value) >= 5:
            ptype, pid, flag_c, flag_d, value_e = struct.unpack(">BBBBB", value[:5])
            return ProgramInfo(
                type=ptype, program_id=pid, flag_c=flag_c, flag_d=flag_d, value_e=value_e
            )
    return None


# ---------------------------------------------------------------- builders


def build_set_lamp(red: int, green: int, blue: int, on: bool) -> bytes:
    """Build SET_LAMP (2317)."""
    return tlv(TLV_LAMP_RGB, struct.pack(">HHH", red, green, blue)) + tlv(
        TLV_LAMP_STATE, bytes([1 if on else 0])
    )


def build_set_clock_display(on: bool, brightness: int) -> bytes:
    """Build SET_CLOCK_DISPLAY (2319 + TLV 2317)."""
    return tlv(TLV_CLOCK_DISPLAY, bytes([1 if on else 0, max(0, min(100, brightness))]))


def build_set_private_mode(on: bool) -> bytes:
    """Build SET_PRIVATE_MODE (2319 + TLV 2059)."""
    return tlv(TLV_PRIVATE_MODE, bytes([0 if on else 1]))


def build_set_alarm_enabled(on: bool) -> bytes:
    """Build SET_ALARM_ENABLED (2331)."""
    return tlv(TLV_ALARM_ENABLED, bytes([1 if on else 0]))


def build_program_settings(settings: dict[int, str]) -> bytes:
    """Build repeated ProgramSetting TLVs."""
    body = b""
    for key, value in settings.items():
        encoded = value.encode("utf-8")
        body += tlv(TLV_PROGRAM_SETTING, bytes([key, len(encoded)]) + encoded)
    return body


def build_start_program(
    program_type: int,
    program_id: int | None = None,
    volume: int | None = None,
    brightness: int | None = None,
    web_radio: str | None = None,
) -> bytes:
    """Build START_PROGRAM (2312)."""
    if program_id is None:
        program_id = DEFAULT_PROGRAM_IDS.get(program_type, 0)
    body = tlv(TLV_PROGRAM_ID, bytes([program_type, program_id & 0xFF]))
    settings: dict[int, str] = {}
    if volume is not None:
        settings[PROGRAM_SETTING_VOLUME] = str(volume)
    if brightness is not None:
        settings[PROGRAM_SETTING_BRIGHTNESS] = str(brightness)
    if web_radio is not None:
        settings[PROGRAM_SETTING_WEB_RADIO] = web_radio
    return body + build_program_settings(settings)


def build_select_program(program_type: int, program_id: int | None = None) -> bytes:
    """Build SELECT_PROGRAM (2307), also used for A2DP media."""
    if program_id is None:
        program_id = DEFAULT_PROGRAM_IDS.get(program_type, 0)
    return tlv(TLV_PROGRAM_ID, bytes([program_type, program_id & 0xFF]))


def build_get_program_settings(program_type: int, program_id: int = 0) -> bytes:
    """Build GET_PROGRAM_SETTINGS (2310)."""
    return tlv(TLV_PROGRAM_TYPE, bytes([program_type]) + struct.pack(">I", program_id))


def build_get_program_info(program_type: int, program_id: int = 0) -> bytes:
    """Build GET_PROGRAM_INFO (2313)."""
    return tlv(TLV_PROGRAM_ID, bytes([program_type, program_id & 0xFF]))


def build_set_program_settings(
    program_type: int,
    volume: int | None = None,
    brightness: int | None = None,
    program_id: int | None = None,
) -> bytes:
    """Build SET_PROGRAM_SETTINGS (2309)."""
    body = tlv(TLV_PROGRAM_TYPE, bytes([program_type]) + struct.pack(">I", 0))
    settings: dict[int, str] = {}
    if volume is not None:
        settings[PROGRAM_SETTING_VOLUME] = str(volume)
    if brightness is not None:
        settings[PROGRAM_SETTING_BRIGHTNESS] = str(brightness)
    if program_id is not None:
        settings[PROGRAM_SETTING_ID] = str(program_id)
    return body + build_program_settings(settings)


def build_time_set(now: datetime, next_change: datetime | None = None) -> bytes:
    """Build TIME_SET (1281), including the next DST transition."""
    offset = int(now.utcoffset().total_seconds()) if now.utcoffset() else 0
    if next_change is None:
        next_change = next_dst_transition(now)
    next_ts = int(next_change.timestamp()) if next_change else 0
    next_offset = (
        int(next_change.utcoffset().total_seconds())
        if next_change and next_change.utcoffset()
        else offset
    )
    return tlv(
        TLV_TIME_SET,
        struct.pack(">IiiI", int(now.timestamp()), offset, next_ts, next_offset),
    )


def build_clock_mode(twelve_hour: bool) -> bytes:
    """Build SET_CLOCK_MODE (2314)."""
    return tlv(TLV_CLOCK_MODE, bytes([1 if twelve_hour else 0]))


def build_set_alarm(
    slot: int,
    hour: int,
    minute: int,
    days: list[str],
    enabled: bool,
    program_id: int,
    one_shot_date: str | None = None,
    volume: int | None = None,
    brightness: int | None = None,
    setting_id: int | None = None,
    web_radio: str | None = None,
) -> bytes:
    """Build SET_ALARM (297)."""
    day = month = year = 0
    if one_shot_date:
        parsed = datetime.strptime(one_shot_date, "%Y-%m-%d")
        day, month, year = parsed.day, parsed.month, parsed.year - 2000
    mask = list_to_days_mask(days)
    if enabled:
        mask |= ALARM_ENABLED_BIT
    alarm = struct.pack(">BBBBBBB", hour, minute, mask, day, month, year, program_id)
    body = tlv(TLV_ALARM_ID, bytes([slot & 0xFF])) + tlv(TLV_SET_ALARM, alarm)
    settings: dict[int, str] = {}
    if volume is not None:
        settings[PROGRAM_SETTING_VOLUME] = str(volume)
    if brightness is not None:
        settings[PROGRAM_SETTING_BRIGHTNESS] = str(brightness)
    if setting_id is not None:
        settings[PROGRAM_SETTING_ID] = str(setting_id)
    if web_radio is not None:
        settings[PROGRAM_SETTING_WEB_RADIO] = web_radio
    return body + build_program_settings(settings)


# ---------------------------------------------------------------- conversions


def lamp_channels(rgb: tuple[int, int, int], brightness: int | None) -> tuple[int, int, int]:
    """Convert HA 8-bit RGB + 0-100 brightness to 16-bit lamp channels."""
    level = 100 if brightness is None else max(0, min(100, brightness))
    scale = 65535.0 * level / 100.0
    return tuple(round(channel * scale / 255.0) for channel in rgb)  # type: ignore[return-value]


def days_mask_to_list(mask: int) -> list[str]:
    """Convert the WPP weekday mask to day names."""
    return [DAYS[i - 1] for i in range(1, 8) if mask & (1 << i)]


def list_to_days_mask(days: list[str]) -> int:
    """Convert day names to the WPP weekday mask."""
    mask = 0
    for day in days:
        if day in DAYS:
            mask |= 1 << (DAYS.index(day) + 1)
    return mask
