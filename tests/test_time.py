"""Timezone/DST tests."""

from __future__ import annotations

import struct
from datetime import datetime
from zoneinfo import ZoneInfo

from custom_components.withings_aura.protocol import build_time_set, decode_tlvs
from custom_components.withings_aura.util import next_dst_transition, time_sync_info


def test_next_dst_transition_europe_rome() -> None:
    tz = ZoneInfo("Europe/Rome")
    now = datetime(2026, 3, 28, 12, 0, tzinfo=tz)
    transition = next_dst_transition(now)
    assert transition is not None
    assert transition.utcoffset().total_seconds() == 7200
    assert transition.date().isoformat() == "2026-03-29"


def test_build_time_set_includes_dst() -> None:
    tz = ZoneInfo("Europe/Rome")
    now = datetime(2026, 3, 28, 12, 0, tzinfo=tz)
    body = build_time_set(now)
    tlvs = decode_tlvs(body)
    assert tlvs[0][0] == 1281
    utc, offset, next_change, next_offset = struct.unpack(">IiiI", tlvs[0][1])
    assert utc == int(now.timestamp())
    assert offset == 3600
    assert next_change > utc
    assert next_offset == 7200


def test_time_sync_info() -> None:
    tz = ZoneInfo("Europe/Rome")
    info = time_sync_info(datetime(2026, 3, 28, 12, 0, tzinfo=tz))
    assert info["utc_offset_text"] == "+01:00"
    assert info["next_offset_text"] == "+02:00"
    assert info["next_change"] is not None
