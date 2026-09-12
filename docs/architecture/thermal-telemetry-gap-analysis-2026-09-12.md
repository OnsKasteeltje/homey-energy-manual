# Thermal telemetry gap analysis — 2026-09-12

Status: **repository preparation only; no runtime or Homey changes**

## Conclusion

The EMS already has the correct historical-storage foundation for thermal learning. The future PV-preheat work should **extend the existing Pi history** rather than create a separate datastore.

A read-only live inventory of `/home/jeroen/ems/data/ems-history.sqlite` on 2026-09-12 confirmed that the installed Pi database contains the expected generic `devices`, `metrics` and `measurements` structures plus derived history tables. It contains 71,872 measurement rows covering 2025-06-24 through 2026-09-12.

The strongest new finding is that the metric registry already contains:

- `room_temperature_c` — `Room temperature reported by Quatt`;
- `room_setpoint_c` — `Room setpoint reported by Quatt`;
- `heating_on` — `Quatt thermostat heating state`.

However, the live measurement coverage currently contains **zero rows** for those three registered metrics. Therefore we should not introduce replacement Honeywell/thermal metric names. The first priority is to populate these already-defined canonical metrics from the least expensive supported source.

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

| Signal | Live device / metric | Coverage observed | Thermal use |
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

Quatt history includes nominal 300-second current data and older entries marked with larger source resolutions such as 21,600 seconds / `historical_6h`. Model fitting must prefer high-resolution `observed` rows and must not silently treat sparse historical rows as equivalent.

## Registered thermal signals not yet populated

The live metric registry already defines the following canonical keys:

| metric_key | Registry description | Live measurements |
|---|---|---:|
| `room_temperature_c` | Room temperature reported by Quatt | 0 |
| `room_setpoint_c` | Room setpoint reported by Quatt | 0 |
| `heating_on` | Quatt thermostat heating state | 0 |

These keys should be reused. Do not create `honeywell_room_temperature_c`, `thermal_room_temperature_c`, `quatt_room_setpoint_c` or similar duplicates unless a future multi-source design explicitly requires source-specific raw staging.

## Remaining gaps before a useful room model can be trained

### G1 — populate current room temperature

The schema is already present as `room_temperature_c`; the missing part is collection. Because the registry describes it as reported by Quatt, first investigate whether the Quatt/Homey device already exposes a targeted Insight/capability for this field or whether an equivalent Pi-local/direct Quatt source exists.

Preferred source order:
1. Pi-local/direct Quatt or Honeywell read-only source if supported;
2. existing compact state publication already produced for another EMS purpose;
3. add the known field to the existing targeted Quatt Insights collector, still at its current hourly batch cadence, only if the first two are unavailable.

Avoid broad Homey device polling.

### G2 — populate current room target

Reuse `room_setpoint_c`. Exact timestamps around naturally occurring setpoint changes are important because these events provide the training examples for `deltaT -> Quatt-only / CV-assist` behaviour.

### G3 — populate heating-demand state

Reuse `heating_on`. This is useful for separating idle thermal drift from active heat-demand intervals and for start/stop event derivation.

### G4 — next scheduled Honeywell target and transition time

No corresponding metric was found in the live registry. Future planning still needs the next scheduled comfort target and transition time, but this is **not required to start passive thermal-response learning**.

Introduce new schedule metrics only after the read source is known and only if no existing compact state already provides them.

### G5 — gas/CV assist evidence

No `cv_assist_active` metric or CV-boiler device was found in the live registry. This remains the most important missing label for supervised Quatt-only-envelope learning.

Need an authoritative or well-validated indication of gas-boiler assist. If no direct boolean exists, an inferred signal may be evaluated later, but inferred and directly observed evidence must use distinct source/quality provenance.

### G6 — event semantics

Need versioned Pi-side derivation for:

- room setpoint transitions;
- Quatt heating start/stop;
- CV-assist start/stop;
- PV surplus start/end;
- room-target reached.

These should be derived from canonical measurements on the Pi where possible; no Homey event flow is required by default.

### G7 — retention and density

Retention is already better than expected: the database spans approximately 15 months overall and includes Quatt thermal data from mid-2025. However, useful high-resolution coverage differs by metric.

For thermal modelling:

- distinguish `observed` from `historical_6h`;
- retain current 300-second Quatt samples at least through a full heating season;
- do not downsample away setpoint/heating/CV transition boundaries;
- 300-second Quatt thermal data is sufficient for the first-order building model; there is no justification for one-minute Homey polling.

## Homey-load assessment

The existing `collect_homey_insights.py` is already targeted to one Quatt device and known log IDs; it does not perform `getDevices()` or `getVariables()` scans. Its timer runs hourly at minute 12 and fetches `last24Hours` data at nominal 300-second resolution.

For thermal work:

- **do not increase that collector to one-minute Homey API polling**;
- reuse the existing Quatt history for the first model baseline;
- first search Pi-local/direct/compact sources for the three already-registered but unpopulated Quatt room metrics;
- if Homey is unavoidable, extend the existing hourly batched Quatt collector rather than create another polling service;
- add no broad device or variable scans;
- use Pi-side event derivation instead of new Homey flows.

## Updated recommended sequence

1. Keep the current SQLite schema and canonical metric keys.
2. Populate existing `room_temperature_c`, `room_setpoint_c` and `heating_on` from the lowest-load source available.
3. Find or derive authoritative `cv_assist_active` evidence.
4. Preserve 300-second observed Quatt data and transition timestamps through the heating season.
5. Build a replay dataset containing natural setpoint changes and corresponding Quatt/CV response.
6. Estimate per-zone / per-outside-temperature `P(CV_ASSIST | deltaT, outsideTemp, ...)` and first-order room thermal response.
7. Add next-schedule metadata for opportunity planning after passive model fitting is viable.
8. Only then add a `PURE_SHADOW` opportunity generator with `executeAllowed=false`.

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

The 2026-09-12 read-only probe reported:

- 71,872 total rows;
- oldest measurement `2025-06-24T06:00:00Z`;
- latest measurement `2026-09-12T16:10:00.501Z`;
- no Honeywell-zone device in the current canonical registry;
- no CV-boiler device in the current canonical registry;
- no measurements yet for registered `room_temperature_c`, `room_setpoint_c` or `heating_on`.

The probe opened SQLite with `mode=ro`, made no Homey API calls and performed no writes.
