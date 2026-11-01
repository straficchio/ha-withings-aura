# Withings Aura for Home Assistant

A local-only Home Assistant custom integration for the **Withings Aura
(WSD01)** bedside unit. It talks directly to the Aura’s WPP-over-TCP bridge on
your LAN — no Withings cloud account, official app, or external Python package.

Tested against firmware **1301** (hardware 12).

## Features

- **Lamp** — colour, brightness, on/off. HA brightness is 0–255; the Aura stores colour and intensity separately. Turning off preserves the last colour/intensity, and turning on resumes it.
- **Program volume** — 0–100 volume for the program selected in the Program select.
- **Clock display** — on/off switch and 0–100 brightness number.
- **Private mode** — switch.
- **Alarms** — per-slot time and enable entities, alarm sensor, global alarm
  switch, and `set_alarm` / `trigger_alarm` / `stop_program` / `snooze` services.
- **Programs** — program select, start button, stop button, snooze button.
- **Status** — playback status, firmware, alarm slots, “playing” binary sensor.
- **Time sync** — DST-aware time/offset sync plus a diagnostic time-offset sensor.
- **Refresh** — a button to force an immediate read (useful after local touch).
- **Local discovery** — mDNS (`_withings-aura-bridge._tcp`), plus manual
  host/port setup.
- **Diagnostics** — redacts the unit’s probe secret.

## Requirements

- Home Assistant **2026.1** or newer.
- The Aura and HA on the same LAN.
- The Aura’s local bridge reachable on TCP port **7685**.
- HACS (recommended) or manual copy of `custom_components/withings_aura`.

## Installation

### HACS (custom repository)

1. HACS → Integrations → three-dot menu → **Custom repositories**.
2. Add `https://github.com/straficchio/ha-withings-aura` as an **Integration**.
3. Install **Withings Aura**.
4. Restart Home Assistant.
5. **Settings → Devices & services → Add integration → Withings Aura**.

### Manual

Copy `custom_components/withings_aura/` into your Home Assistant config:

```text
<config>/custom_components/withings_aura/
```

Restart Home Assistant, then add the integration.

## Configuration

The integration should be discovered automatically via mDNS. If it is not,
choose **Withings Aura** from the add-integration dialog and enter the bridge
host and port (default `7685`).

The unit is identified by the MAC address reported by its `PROBE` reply. A
unit that answers with a `ProbeChallenge` (command 296) requires the Withings
association secret; the config flow aborts with a clear error rather than
creating a half-working entry.

### Options

- **Status poll interval** — default 10 s (5–300 s).
- **Alarm/program poll interval** — default 300 s (60–3600 s).

## Entities

| Entity | Type | Description |
|---|---|---|
| Lamp | `light` | RGB colour, brightness, on/off |
| Clock display | `switch` | Clock display on/off |
| Clock brightness | `number` | 0–100 |
| Program volume | `number` | 0–100 for the selected program |
| Private mode | `switch` | Aura private mode |
| Alarms | `switch` | Global alarm enable |
| Alarms | `sensor` | Configured alarms and attributes |
| Alarm slots | `sensor` | Number of alarm slots (diagnostic) |
| Alarm time 1–10 | `time` | Time for each alarm slot |
| Alarm 1–10 | `switch` | Enable/disable each alarm slot |
| Time offset | `sensor` | Current UTC offset and next DST transition (diagnostic) |
| Firmware | `sensor` | Firmware version (diagnostic) |
| Status | `sensor` | Idle/sleep/nap/wake-up/mood/media |
| Playing | `binary_sensor` | A program is playing |
| Program | `select` | Mood, Nap, Sleep, Wake-up, Retail, Media |
| Start program | `button` | Starts the selected program |
| Trigger alarm | `button` | Starts a wake-up program immediately |
| Stop program | `button` | Stops the current program |
| Snooze | `button` | Snoozes the current wake-up |
| Sync time | `button` | Pushes HA time/clock mode |
| Refresh | `button` | Forces an immediate coordinator refresh |

## Time sync

The integration uses Home Assistant’s configured timezone. **Sync time** sends
the current UTC time, the current UTC offset, the next DST transition, and the
next UTC offset. The **Time offset** diagnostic sensor shows what was sent. To
change the timezone, change Home Assistant’s timezone and press **Sync time**;
there is no separate Aura timezone setting.

## Local touch

The Aura is polled every 10 seconds by default. Press **Refresh** for an
immediate read after touching the lamp. `GET_LAMP` returns the actual colour
and the on/off state byte; the integration uses that state byte rather than
assuming “colour > 0 means on”. If the lamp still does not update, the firmware
is not exposing its local touch state through `GET_LAMP`.

## Services

Volume is stored per program. The **Program volume** number applies to the
program currently selected in the **Program** select. Alarm volume is set per
alarm with the `set_alarm` service.

All services accept an optional `entry_id`; omit it when only one Aura is
configured.

### `withings_aura.start_program`

```yaml
service: withings_aura.start_program
data:
  program_type: nap
  program_id: 1
  volume: 50
  brightness: 97
```

`program_type` is one of `mood`, `nap`, `sleep`, `wake_up`, `retail`, `media`.

### `withings_aura.set_alarm`

```yaml
service: withings_aura.set_alarm
data:
  slot: 1
  time: "06:45"
  days: [mon, tue, wed, thu, fri]
  program_id: 15
  enabled: true
  volume: 46
  brightness: 50
```

`days` uses `mon`…`sun`; leave it empty for a one-shot alarm and set
`one_shot_date: "2026-11-01"` if needed. For the UI, set the time with the
**Alarm N time** entity and toggle **Alarm N**; use this service when you need
to change the weekday mask, program or volume.

### `withings_aura.trigger_alarm`

```yaml
service: withings_aura.trigger_alarm
data:
  program_id: 15
  volume: 50
  brightness: 50
```

### `withings_aura.stop_program`

```yaml
service: withings_aura.stop_program
```

### `withings_aura.snooze`

```yaml
service: withings_aura.snooze
```

### `withings_aura.set_alarm_enabled`

```yaml
service: withings_aura.set_alarm_enabled
data:
  enabled: true
```

### `withings_aura.set_clock_display`

```yaml
service: withings_aura.set_clock_display
data:
  display: true
  brightness: 55
```

### `withings_aura.sync_time`

```yaml
service: withings_aura.sync_time
data:
  twelve_hour: false
```

### `withings_aura.set_program_settings`

```yaml
service: withings_aura.set_program_settings
data:
  program_type: sleep
  volume: 29
  brightness: 50
  program_id: 1
```

## Example automations

Turn the lamp on at sunset:

```yaml
automation:
  - alias: Aura mood light at sunset
    triggers:
      - trigger: sun
        event: sunset
    actions:
      - action: light.turn_on
        target:
          entity_id: light.withings_aura_lamp
        data:
          rgb_color: [255, 140, 80]
          brightness: 20
```

Trigger the wake-up alarm from an automation:

```yaml
actions:
  - action: withings_aura.trigger_alarm
    data:
      program_id: 15
      volume: 50
```

## Troubleshooting

- **Cannot connect** — confirm the Aura is on the same LAN and that TCP 7685
  is reachable. The integration uses the address from mDNS; use the manual
  flow if mDNS is blocked.
- **`unsupported_auth`** — the unit answered with a `ProbeChallenge` and
  requires the Withings association secret. Local control is not available
  for that unit without the secret.
- **Lamp writes feel delayed** — the firmware fades and rate-limits colour
  writes. The integration debounces rapid changes, sends writes serially, and
  refreshes after a short delay.
- **Status not updating** — check the options poll interval and the HA log for
  `withings_aura` connection errors.

## Limitations

- Cloud-only data (sleep history, environment graphs, resting heart rate) is
  not exposed.
- No Spotify playback control and no A2DP switch in v1.
- No firmware flashing, Wi-Fi reconfiguration, factory reset, or sleep-sensor
  association.
- The protocol is undocumented and may change with firmware; this integration
  is tested against firmware 1301.

## Development

```bash
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python pytest pytest-asyncio \
  pytest-homeassistant-custom-component ruff
.venv/bin/pytest
.venv/bin/ruff check custom_components tests
```

The protocol layer is pure Python and covered by golden-frame tests; the HA
layer uses a fake TCP bridge so tests do not need a real Aura.

## License

MIT. See [LICENSE](LICENSE).

This is an independent interoperability project, not affiliated with or
endorsed by Withings.
