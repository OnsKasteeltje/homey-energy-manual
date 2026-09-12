# Thermal telemetry gap analysis — 2026-09-12

Status: **repository preparation only; no runtime or Homey changes**

## Conclusion

The EMS already has the correct historical-storage foundation for thermal learning. The future PV-preheat work should **extend the existing Pi history** rather than create a separate datastore.

A read-only live inventory of `/home/jeroen/ems/data/ems-history.sqlite` on 2026-09-12 confirmed that the installed Pi database contains the expected generic `devices`, `metrics` and `measurements` structures plus derived history tables. It contains 71,872 measurement rows covering 2025-06-24 through 2026-09-12.

The strongest live findings are:

- the metric registry already contains `room_temperature_c`, `room_setpoint_c` and `heating_on`, but none of these has measurement rows yet;
- the existing canonical `energy-state-v2.json` already publishes Quatt state including `thermostat_heating_on`, `cv_requested`, `cv_flame`, Quatt electrical/thermal power, COP and working modes;
- the live Core obtains the Quatt device once as part of its existing targeted device batch and derives these Quatt fields from that already-fetched object, so exposing additional Quatt capability values in the canonical state need not add an extra Homey device read;
- `cv_requested` is already available as evidence, but it must **not** automatically be treated as equivalent to actual gas flame / CV assist. `cv_flame` is currently `null` in the canonical state and must remain semantically distinct.

Therefore the next step is not to create another poller. First reuse the existing canonical state and existing Quatt batch read as far as possible, then only add targeted collection where a required field is genuinely absent.

## Live canonical store confirmed

Tables observed:

- `devices`
- `metrics`
- `measurements`
- `measurements_15m`
- `daily_energy_history`
- `forecast_weather_15m`
- `forecast_ww_daily`
- `tesla_connection_events`

Relevant measurement columns are:

- `ts_utc`
- `device_id`
- `metric_id`
- `value_real`
- `value_text`
- `quality`
- `source_resolution_seconds`
- `collected_at_utc`

This is sufficient for thermal-model provenance and data-quality filtering without a new primary datastore.

## Existing signals confirmed live

| Signal | Live device / metric or canonical state | Coverage observed | Thermal use |
|---|---|---:|---|
| P1 net power | `grid_p1 / electrical_power_w` | 2026-08-23 → current, 300 s | actual import/export and residual PV validation |
| PV SolarEdge | `pv_solaredge / electrical_power_w` | 2026-08-19 → current, 300 s | aggregate PV reconstruction |
| PV GoodWe 4200 | `pv_goodwe4200 / electrical_power_w` | 2026-08-19 → current, 300 s | aggregate PV reconstruction |
| PV GoodWe 2000 | `pv_goodwe2000 / electrical_power_w` | 2026-08-19 → current, 300 s | aggregate PV reconstruction |
| Tesla charging | `tesla / electrical_power_w` | 2026-08-19 → current, 300 s | replay priority allocation |
| WW boiler | `boiler / electrical_power_w` | 2026-02-26 → current, mixed 60 s / held / historical | replay priority allocation |
| Quatt electrical power | `quatt_cic / electrical_power_w` | 2025-12-31 → current | heat-pump electricity input |
| Quatt outside temperature | `quatt_cic / outside_temperature_c` | 2025-12-31 → current | principal thermal/weather feature |
| Quatt HP2 outside temperature | `quatt_cic / hp2_outside_temperature_c` | 2025-06-24 → current | alternate/direct thermal-weather feature |
| Quatt HP1 thermal power | `quatt_cic / hp1_thermal_power_w` | 2025-08-23 → current | thermal response / COP analysis |
| Quatt HP2 thermal power | `quatt_cic / hp2_thermal_power_w` | 2025-08-23 → current | thermal response / COP analysis |
| Quatt HP1 COP | `quatt_cic / hp1_cop` | 2025-08-23 → current | efficiency / shift value |
| Quatt HP2 COP | `quatt_cic / hp2_cop` | 2025-08-23 → current | efficiency / shift value |
| thermostat demand | `energy-state-v2.json -> quatt.thermostat_heating_on` | current canonical state | separates thermostat demand from idle drift |
| CV request | `energy-state-v2.json -> quatt.cv_requested` | current canonical state | candidate assist/request feature, **not actual flame proof** |
| CV flame | `energy-state-v2.json -> quatt.cv_flame` | field exists, currently null | preferred direct gas-assist evidence if it becomes reliable |

Quatt history includes nominal 300-second current data and older entries marked with larger source resolutions such as 21,600 seconds / `historical_6h`. Model fitting must prefer high-resolution `observed` rows and must not silently treat sparse historical rows as equivalent.

## Registered thermal signals not yet populated

The live metric registry already defines the following canonical keys:

| metric_key | Registry description | Live measurements |
|---|---|---:|
| `room_temperature_c` | Room temperature reported by Quatt | 0 |
| `room_setpoint_c` | Room setpoint reported by Quatt | 0 |
| `heating_on` | Quatt thermostat heating state | 0 |

These keys should be reused. Do not create `honeywell_room_temperature_c`, `thermal_room_temperature_c`, `quatt_room_setpoint_c` or similar duplicates unless a future multi-source design explicitly requires source-specific raw staging.

`heating_on` can likely be populated from the already-published canonical `quatt.thermostat_heating_on` without any additional Homey call.

## Remaining gaps before a useful room model can be trained

### G1 — populate current room temperature

The schema is already present as `room_temperature_c`; the missing part is collection. Because the registry describes it as reported by Quatt, first determine whether the already-fetched Quatt device object used by Core contains the room-temperature capability. If yes, publish it in the existing canonical state and ingest it on the Pi; this adds **no extra Quatt `getDevice()` call**.

Preferred source order:
1. value already present in the Quatt device object fetched by the existing Core batch;
2. Pi-local/direct Quatt or Honeywell read-only source if supported;
3. existing compact state publication already produced for another EMS purpose;
4. add the known field to the existing targeted Quatt Insights collector, still at its current hourly batch cadence, only if the first three are unavailable.

Avoid broad Homey device polling.

### G2 — populate current room target

Reuse `room_setpoint_c`. As with room temperature, first check whether the existing Core Quatt object already contains the target/setpoint capability and, if so, fan it out through `energy-state-v2` without another Homey read.

Exact timestamps around naturally occurring setpoint changes are important because these events provide training examples for `deltaT -> Quatt-only / CV-assist` behaviour.

### G3 — populate heating-demand state

Reuse `heating_on`. The current canonical state already carries `quatt.thermostat_heating_on`, so Pi-side ingestion should be preferred over any new Homey collector.

### G4 — next scheduled Honeywell target and transition time

No corresponding metric was found in the live registry. Future planning still needs the next scheduled comfort target and transition time, but this is **not required to start passive thermal-response learning**.

Introduce new schedule metrics only after the read source is known and only if no existing compact state already provides them.

### G5 — gas/CV assist evidence

The earlier inventory found no `cv_assist_active` metric or CV-boiler device in the SQLite registry, but the canonical state already exposes two important Quatt-side fields:

- `cv_requested` from `measure_boiler_cic_central_heating_on`;
- `cv_flame` from `measure_boiler_flame_on`, currently nullable.

These semantics must stay separate:

- `cv_requested=true` means the Quatt/CIC path is requesting central-heating boiler participation;
- `cv_flame=true` would be much stronger evidence of actual burner activity if reliable;
- `cv_flame=null` is unknown and must never be interpreted as false.

For first modelling we can store `cv_requested` as an observed feature. We should only create/derive `cv_assist_active` once we have validated which combination of `cv_requested`, `cv_flame`, gas data and/or boiler telemetry reliably means actual gas assist.

### G6 — event semantics

Need versioned Pi-side derivation for:

- room setpoint transitions;
- thermostat heating demand start/stop;
- Quatt compressor/thermal-output start/stop;
- CV request start/stop;
- actual CV assist start/stop once an authoritative signal is validated;
- PV surplus start/end;
- room-target reached.

These should be derived from canonical measurements/state on the Pi where possible; no Homey event flow is required by default.

### G7 — retention and density

Retention is already better than expected: the database spans approximately 15 months overall and includes Quatt thermal data from mid-2025. However, useful high-resolution coverage differs by metric.

For thermal modelling:

- distinguish `observed` from `historical_6h`;
- retain current 300-second Quatt samples at least through a full heating season;
- do not downsample away setpoint/heating/CV transition boundaries;
- 300-second Quatt thermal data is sufficient for the first-order building model; there is no justification for one-minute Homey polling.

## Homey-load assessment

The existing `collect_homey_insights.py` is already targeted to one Quatt device and known log IDs; it does not perform `getDevices()` or `getVariables()` scans. Its timer runs hourly at minute 12 and fetches `last24Hours` data at nominal 300-second resolution.

More importantly, the current Core already fetches the Quatt device as one member of its existing targeted device batch and derives `thermostat_heating_on`, `cv_requested`, `cv_flame`, Quatt power, thermal power, COP and working modes from that object. Therefore:

- **do not add a second frequent Quatt device read**;
- fan out additional already-present Quatt capabilities through the existing canonical state when possible;
- ingest canonical state into SQLite on the Pi;
- use Insights only for historical backfill or fields that cannot be exposed through the current Core read;
- do not increase the existing collector to one-minute Homey API polling;
- add no broad device or variable scans;
- use Pi-side event derivation instead of new Homey flows.

## Updated recommended sequence

1. Keep the current SQLite schema and canonical metric keys.
2. Populate `heating_on` immediately from existing canonical `quatt.thermostat_heating_on` on the Pi side.
3. Determine the exact Quatt capability names for room temperature and room setpoint from the already-fetched Core device object; if present, add them to the existing canonical state without an extra Homey read.
4. Persist `cv_requested` as a distinct observed feature; do not relabel it as actual CV assist.
5. Validate whether `cv_flame` can become an authoritative burner signal; otherwise correlate with gas/boiler evidence before deriving `cv_assist_active`.
6. Preserve 300-second observed Quatt data and transition timestamps through the heating season.
7. Build a replay dataset containing natural setpoint changes and corresponding Quatt/CV response.
8. Estimate per-zone / per-outside-temperature `P(CV_ASSIST | deltaT, outsideTemp, ...)` and first-order room thermal response.
9. Add next-schedule metadata for opportunity planning after passive model fitting is viable.
10. Only then add a `PURE_SHADOW` opportunity generator with `executeAllowed=false`.

## What is deliberately not prepared yet

- no Honeywell write adapter;
- no OpenTherm integration or manipulation;
- no new Homey flow;
- no new systemd timer;
- no active planner code;
- no threshold for a "safe" setpoint delta;
- no assumption that all zones share the same thermal response;
- no authority/cutover change.

These omissions are intentional. The repository rule in `src/pi/README.md` requires accepted planner logic to be tested first in the active Pi runtime before synchronization back to GitHub.

## Live inventory evidence

The 2026-09-12 read-only probes reported:

- 71,872 total SQLite measurement rows;
- oldest measurement `2025-06-24T06:00:00Z`;
- latest measurement `2026-09-12T16:10:00.501Z`;
- no Honeywell-zone device in the current canonical registry;
- no CV-boiler device in the current canonical registry;
- no measurements yet for registered `room_temperature_c`, `room_setpoint_c` or `heating_on`;
- local canonical state already contains Quatt thermostat/CV-request fields;
- broad filesystem scan found the active thermal references in `energy-state-v2.json`, Core sources and planner files without making Homey or network calls.

Both probes were read-only and performed no Homey API calls or writes.
