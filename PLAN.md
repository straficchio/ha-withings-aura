# Plan: Home Assistant integration for Withings Aura (WSD01)

Status: **implemented v0.1.4** (M0–M4); M5 is optional.
Target: a self-contained, HACS-shareable custom integration in this folder.
Protocol reference: the WPP notes in the parent reverse-engineering workspace
(not part of this repository). The integration is self-contained.

## 1. Goal

Create `withings_aura`, a local-only Home Assistant custom integration that
controls the Aura bedside unit over its WPP TCP bridge (port 7685), with no
Withings cloud account and no external Python package.

The integration must be deployable by copying
`custom_components/withings_aura/` into Home Assistant’s config directory, and
shareable as a standalone HACS repository rooted at this folder.

Non-goals for v1:

- sleep/environment history (cloud-only)
- Spotify playback control (the unit exposes a separate Spotify Connect API)
- routing Bluetooth A2DP audio through Home Assistant
- firmware flashing, Wi-Fi reconfiguration, factory reset
- replacing the official app for account/association management

## 2. Product decisions

| Decision | Recommendation |
|---|---|
| Domain | `withings_aura` |
| Integration type | `device` (one config entry per Aura) |
| IoT class | `local_polling` |
| Config flow | mDNS discovery + manual host/port fallback |
| External dependencies | none; vendor the WPP client |
| Poll interval | 10 s default, configurable 5–300 s |
| Slow poll (alarms/programs) | every 5 min |
| License | MIT |
| Sharing | HACS custom repository; not core (undocumented protocol) |
| Raw WPP service | not exposed |
| A2DP/media switch | deferred to M5; not in v1 |

## 3. Repository layout

This folder is the repository root. The integration itself is the only thing
HACS installs.

```text
ha-withings-aura/
├── PLAN.md
├── README.md
├── LICENSE
├── hacs.json
├── custom_components/
│   └── withings_aura/
│       ├── __init__.py
│       ├── manifest.json
│       ├── const.py
│       ├── models.py
│       ├── protocol.py          # WPP framing, TLVs, codecs
│       ├── transport.py         # async TCP bridge, reconnect, request lock
│       ├── device.py            # typed probe/read/write API
│       ├── exceptions.py        # AuraError/connection/timeout
│       ├── util.py              # MAC/time helpers
│       ├── coordinator.py       # DataUpdateCoordinator + snapshot
│       ├── config_flow.py       # zeroconf + manual + options
│       ├── entity.py            # base entity/device info
│       ├── light.py             # lamp
│       ├── switch.py            # clock display, private mode, alarm, media
│       ├── number.py            # clock brightness
│       ├── select.py            # program type
│       ├── button.py            # start/stop/snooze/sync time
│       ├── sensor.py            # status, firmware, alarms, diagnostics
│       ├── services.py          # YAML services
│       ├── services.yaml
│       ├── diagnostics.py
│       ├── strings.json
│       ├── translations/en.json
│       └── brand/icon.png
├── tests/
│   ├── conftest.py
│   ├── fake_bridge.py
│   ├── test_protocol.py
│   ├── test_transport.py
│   ├── test_config_flow.py
│   ├── test_light.py
│   ├── test_switches.py
│   └── test_services.py
└── .github/workflows/
    ├── hassfest.yml
    ├── hacs.yml
    └── tests.yml
```

**Self-containment rule:** `custom_components/withings_aura/` must never import
from `../tools` or `../docs`. Port the relevant client code into `protocol.py`
and `transport.py`, and keep test fixtures inside `tests/`.

## 4. Architecture

### 4.1 Protocol layer (`protocol.py`)

Pure functions and dataclasses, no I/O:

- `encode_wpp(cmd, tlvs) -> bytes`
- `decode_wpp(data) -> WppMessage`
- `encode_tlv/decode_tlvs`
- `frag_wrap/frag_parse`
- codecs for `ProbeReply`, `Status`, `LampState`, `Settings`, `Alarm`,
  `ProgramInfo`, `ProgramSetting`
- conversions:
  - HA RGB/brightness ↔ 16-bit lamp channels
  - alarm weekday mask ↔ HA day names
  - program type/id ↔ names

Constants in `const.py`: command numbers, TLV ids, status/substatus/program
enums, program-setting keys.

### 4.2 Transport layer (`transport.py`)

One `AuraBridge` per config entry:

- `asyncio.open_connection(host, 7685)`
- one reader task parsing FragFsm frames (including partial reads)
- one `asyncio.Lock` serializing requests (the bridge is effectively
  single-session)
- `async_request(cmd, tlvs, timeout=5)` resolves by matching command
- reconnect with backoff `1, 2, 5, 10, 30 s`
- send `DISCONNECT` (272) on unload
- log unsolicited frames at debug level
- never block the event loop

### 4.3 Coordinator (`coordinator.py`)

`AuraCoordinator(DataUpdateCoordinator[AuraSnapshot])`:

- setup: connect, `PROBE` (257), validate MAC/firmware
- fast poll: `GET_STATUS` (2311), `GET_LAMP` (2318), `GET_SETTINGS` (2320)
- slow poll: `GET_ALARMS` (293), `GET_ALARM_ENABLED` (2330),
  `GET_PROGRAM_SETTINGS` (2310) for the selected types
- `AuraSnapshot` dataclass with `probe`, `status`, `lamp`, `settings`,
  `alarm_enabled`, `alarms`, `programs`, `last_seen`
- `async_write` helper: serialize, send, optimistic update, refresh after a
  short delay
- `UpdateFailed` on timeout; `ConfigEntryNotReady` on initial connect failure

### 4.4 Entities

| Platform | Entity | WPP | Notes |
|---|---|---|---|
| `light` | Lamp | 2318 read / 2317 write | RGB + brightness + off |
| `switch` | Clock display | 2320 read / 2319+2317 write | |
| `number` | Clock brightness | 2320 read / 2319+2317 write | 0–100 |
| `number` | Program volume | 2310 read / 2309 write | selected program, 0–100 |
| `switch` | Private mode | 2320 read / 2319+2059 write | inverted |
| `switch` | Alarm enabled | 2330 / 2331 | global flag |
| `time` | Alarm 1–10 time | 293 / 297 | per-slot time |
| `switch` | Alarm 1–10 enabled | 293 / 297 | per-slot enable |
| `select` | Program | 2310/2313 | mood, nap, sleep, wake-up, retail, media |
| `button` | Start program | 2312 | uses select + optional settings |
| `button` | Trigger alarm | 2312 (type 4) | starts a wake-up program |
| `button` | Stop program | 2308 | |
| `button` | Snooze | 2321 | |
| `button` | Sync time | 1281 | |
| `sensor` | Status | 2311 | enum + substatus |
| `sensor` | Firmware | 257 | diagnostic |
| `sensor` | Alarm count | 298 | diagnostic |
| `sensor` | Alarms | 293 | attributes; v1 |
| `sensor` | Time offset | 1281 | timezone/DST diagnostic |
| `binary_sensor` | Playing | 2311 | optional |

**Light semantics:**

- `is_on` = any of R/G/B > 0 (the state byte is unreliable).
- `brightness` = `max(R,G,B) / 65535 * 100`.
- `rgb_color` = each channel / 257 (16-bit → 8-bit).
- turn on: scale HA RGB by requested brightness to 16-bit channels, state 1.
- turn off: send `000000` + state 0.
- debounce rapid colour-picker updates ~250 ms; use optimistic state and
  refresh after the firmware fade settles.

### 4.5 Config flow

`config_flow.py`:

1. **zeroconf** — `_withings-aura-bridge._tcp.local.`; read TXT `mac`,
   `version`, `host`, `port`; normalize MAC as unique id; confirm.
2. **user** — manual host/port; validate with `PROBE`; derive unique id from
   the probe MAC. If the unit answers with command 296 (`ProbeChallenge`),
   abort with an `unsupported_auth` message instead of creating a half-working
   entry.
3. **reconfigure** — change host/port.
4. **options** — poll interval and slow-poll interval.

`manifest.json` includes:

```json
{
  "domain": "withings_aura",
  "name": "Withings Aura",
  "codeowners": ["@straficchio"],
  "config_flow": true,
  "documentation": "https://github.com/YOUR_GITHUB_HANDLE/ha-withings-aura",
  "integration_type": "device",
  "iot_class": "local_polling",
  "issue_tracker": "https://github.com/YOUR_GITHUB_HANDLE/ha-withings-aura/issues",
  "requirements": [],
  "version": "0.1.0",
  "zeroconf": ["_withings-aura-bridge._tcp.local."]
}
```

`hacs.json`:

```json
{
  "name": "Withings Aura",
  "render_readme": true,
  "homeassistant": "2026.1.0"
}
```

### 4.6 Services

`services.yaml` + `services.py`:

- `withings_aura.start_program` — type, id, volume, brightness, web_radio
- `withings_aura.stop_program`
- `withings_aura.snooze`
- `withings_aura.trigger_alarm` — start a wake-up program immediately
- `withings_aura.set_alarm` — slot, time, days, program, volume, brightness,
  enabled
- `withings_aura.set_alarm_enabled` — boolean
- `withings_aura.set_clock_display` — on, brightness
- `withings_aura.sync_time`
- `withings_aura.set_program_settings` — type, volume, brightness, id

### 4.7 Diagnostics

`diagnostics.py` returns probe/status/lamp/settings/alarms/program info and
entity states, redacting `ProbeReply.secret` and any user-specific data.

## 5. Testing strategy

### Unit / protocol

- golden frames from the live capture:
  - probe request/reply
  - status reply
  - lamp read/write
  - settings read
  - alarm read
  - program settings/info
- encode/decode round trips
- partial FragFsm reads and multiple frames per TCP read
- RGB/brightness conversions
- alarm weekday mask conversions

### Fake bridge

`tests/fake_bridge.py` — `asyncio.start_server` on localhost that:

- validates the `u16 + FragFsm + WPP` envelope
- replays captured responses by command
- can simulate timeout, reset, partial frame, unsolicited frame
- records writes for assertions

### Home Assistant tests

Use `pytest-homeassistant-custom-component`:

- config flow: zeroconf, manual, duplicate unique id, invalid host
- setup/unload, `ConfigEntryNotReady` on connect failure
- light turn on/off/colour/brightness and debounce
- clock display switch + brightness number
- private mode inversion
- alarm enabled switch and alarm sensor attributes
- program select/start/stop/snooze services
- coordinator reconnect after fake bridge drop
- diagnostics redaction

### Manual acceptance

1. Copy `custom_components/withings_aura` to HA, restart.
2. Aura is discovered automatically; add it; entities appear.
3. Lamp colour/brightness/off works and survives an HA restart.
4. Clock display switch and brightness work.
5. Private mode toggles.
6. Alarm list matches the app.
7. Stop/snooze/start program work.
8. Pull the Aura’s network cable / power-cycle it; integration reconnects.
9. No blocking-I/O warnings in the HA log.

## 6. Milestones

### M0 — Protocol extraction (1–2 days)

- Create `protocol.py`, `models.py`, `const.py`.
- Port the working client from `../tools/aura.py`.
- Add fake bridge + protocol unit tests.
- Sanitize the test MAC/IP in fixtures.

**Done when:** the fake bridge passes probe/status/lamp/settings/alarm tests,
and no integration code imports from `../tools`.

### M1 — Skeleton, config flow, coordinator, light (2–3 days)

- `manifest.json`, `__init__.py`, `config_flow.py`, `coordinator.py`,
  `entity.py`, `light.py`, `sensor.py`.
- mDNS + manual setup.
- Lamp entity and status/firmware sensors.

**Done when:** HA discovers/adds the Aura, the lamp is controllable, and
status/firmware update.

### M2 — Settings and program controls (1–2 days)

- Clock display switch, brightness number, program volume number, private mode switch.
- Per-slot alarm time and enable entities.
- Program select, start/stop/snooze buttons.
- Alarm enabled switch, alarm sensor.

**Done when:** all read/write entities in the table work and refresh correctly.

### M3 — Alarms, services, diagnostics (2–3 days)

- `set_alarm`, `set_program_settings`, `sync_time`, `set_clock_display`.
- Diagnostics with redaction.
- Options flow.

**Done when:** alarm service can create/update a slot without corrupting the
existing alarms, and diagnostics contain no secret.

### M4 — HACS/share polish (1–2 days)

- `hacs.json`, `LICENSE`, `README`, translations, brand icon.
- CI: hassfest, HACS validation, pytest, ruff.
- Version `0.1.0`, changelog.
- Remove the test unit’s MAC/IP from public docs.

**Done when:** a fresh HA install can add the repo via HACS, install, restart,
and discover the Aura.

### M5 — Optional advanced (2–3 days)

- Alarm calendar entity.
- Program preset selectors / web-radio and Spotify presets.
- A2DP media switch (deferred from v1).
- `media_player` only if a practical audio path is found.

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Undocumented protocol / firmware changes | pin tested firmware 1301 in docs; keep protocol isolated; feature-detect where possible |
| Some units may answer `PROBE` with a challenge (296) and require the association secret/KL | detect this in config flow, abort with a clear “unit requires authentication” message, and document it; do not pretend writes are supported |
| Lamp writes are rate-limited/faded | debounce, serialize, optimistic state, delayed refresh, retry |
| One TCP session only | one bridge + one request lock per entry; no parallel requests |
| mDNS discovery unreliable | manual host/port flow; reconfigure |
| Brightness semantics differ from app | use max channel for HA brightness; document |
| Alarm encoding ambiguity | fixture-based tests; only write alarms via explicit service |
| A2DP audio cannot be routed by HA | no A2DP switch in v1; revisit in M5 |
| Sharing leaks user data | sanitize MAC/IP/secret in docs, fixtures, diagnostics |
| HACS validation | run hassfest/HACS actions before tagging |

## 8. Resolved decisions

1. Domain: `withings_aura`.
2. Alarm model: alarm sensor + `set_alarm` / `trigger_alarm` / `stop_program`
   services.
3. A2DP/media switch: deferred to M5; not in v1.
4. Raw WPP service: not exposed.
5. Default poll interval: 30 s, configurable in options.
6. License: MIT.
7. Program control: select + start button.

## 9. First implementation PR

1. Add `custom_components/withings_aura/{manifest.json,const.py,protocol.py,
   models.py,transport.py}`.
2. Port the probe/status/lamp/settings codecs from `../tools/aura.py`.
3. Add `tests/fake_bridge.py` + `tests/test_protocol.py`.
4. Add a minimal `config_flow.py` (manual host/port + probe validation).
5. Add `coordinator.py` + `light.py` + `sensor.py` (status/firmware).
6. Verify with `pytest` and a local HA dev instance.

Once that PR is green, the rest of the entities/services are mostly
mechanical mappings over the same coordinator and protocol layer.

## 10. Definition of done (v0.1.0)

- [ ] `custom_components/withings_aura/` has no imports from the parent workspace.
- [ ] mDNS discovery and manual setup both work; duplicate entries are rejected by MAC.
- [ ] Lamp, clock display, clock brightness and private mode entities work.
- [ ] Status/firmware sensors update on the configured interval.
- [ ] Alarm list and global alarm switch work.
- [ ] Program select + start/stop/snooze buttons work.
- [ ] `set_alarm` and `set_program_settings` services work and validate input.
- [ ] Integration reconnects after the Aura drops off the network.
- [ ] No blocking I/O warnings; writes are serialized and debounced.
- [ ] Diagnostics redact the probe secret and user-specific data.
- [ ] `pytest`, hassfest and HACS validation are green.
- [ ] README, translations, license and version are present; no real MAC/IP in
      public fixtures or screenshots.
- [ ] A fresh HA + HACS install can add the repository, install, restart,
      discover the Aura and control the lamp.
