# Thermal telemetry gap analysis — 2026-09-12

Status: **repository preparation only; no runtime or Homey changes**

## Conclusion

The EMS already has the correct historical-storage foundation for thermal learning. The future PV-preheat work should **extend the existing Pi history** rather than create a separate datastore.

The repository currently shows:

- canonical SQLite history at `/home/jeroen/ems/data/ems-history.sqlite`;
- generic `devices`, `metrics` and `measurements` concepts;
- per-measurement quality and source-resolution metadata;
- Homey EM2 day-history import for P1, PV, Tesla, boiler and appliance state;
- an existing targeted Quatt Insights collector for electrical power, outside temperature, two thermal-power channels and COP;
- an hourly systemd timer for that targeted Quatt collector, which fetches a 24-hour window and stores nominal 300-second samples.

This is enough to prepare thermal modelling without changing the storage architecture.

## Existing signals that can already be reused

| Signal | Existing repository path / metric | Thermal use |
|---|---|---|
| P1 net power | `grid_p1 / electrical_power_w` via `import_em2_day_history.py` | detect actual import/export and validate PV surplus |
| PV inverter power | existing SolarEdge / GoodWe imports | reconstruct aggregate PV and residual surplus |
| Tesla charging power | `tesla / electrical_power_w` | identify EV consumption and replay priority allocation |
| WW boiler power | `boiler / electrical_power_w` | identify WW consumption and replay priority allocation |
| Quatt electrical power | `quatt_cic / electrical_power_w` via `collect_homey_insights.py` | heat-pump electricity input |
| Quatt outside temperature | `quatt_cic / outside_temperature_c` | principal thermal/weather feature |
| Quatt thermal power | `hp1_thermal_power_w`, `hp2_thermal_power_w` | thermal response / COP analysis |
| Quatt COP | `hp1_cop`, `hp2_cop` | assess value of shifting heat to PV-rich periods |

Do not introduce duplicate thermal-specific metric names for these existing values.

## Gaps before a useful room model can be trained

### G1 — per-zone room temperature

Need a stable zone identity and `room_temperature_c` history.

Preferred source order:
1. direct/local Honeywell source if a supported read-only interface is available;
2. already-published targeted state;
3. targeted Homey capability/Insight only if unavoidable.

Avoid broad device polling.

### G2 — per-zone current target

Need `room_target_c` with exact timestamps around changes. This is needed both for thermal-response fitting and to detect naturally occurring small/large target deltas.

### G3 — next scheduled Honeywell target and transition time

Need `next_scheduled_target_c` and `next_scheduled_target_at` for future opportunity planning. This is not required to start passive thermal-response learning if it is initially unavailable.

### G4 — gas/CV assist evidence

Need an authoritative or well-validated `cv_assist_active` signal. This is critical because the learned objective is not merely "room warmed" but specifically "Quatt-only heating without causing gas assist".

If no direct boolean exists, an inferred signal may be evaluated later, but inferred and directly observed evidence must not be mixed without quality/source labels.

### G5 — event semantics

Need versioned event derivation for setpoint transitions, Quatt starts/stops and CV-assist starts/stops. These can be derived from measurements on the Pi if timestamps/resolution are sufficient; no Homey event flow is required by default.

### G6 — longer-term retention validation

The canonical database is structurally suitable, but repository inspection alone does not prove installed retention/cleanup policy on the running Pi. Before model fitting, verify that detailed transition data is retained long enough to span multiple outside-temperature regimes, ideally at least one heating season.

## Homey-load assessment

The existing `collect_homey_insights.py` is already targeted to one Quatt device and known log IDs; it does not perform `getDevices()` or `getVariables()` scans. Its timer runs hourly at minute 12 and fetches `last24Hours` data at nominal 300-second resolution.

For thermal work:

- **do not increase that collector to one-minute Homey API polling**;
- reuse its existing Quatt history for the first model baseline;
- add new Honeywell data through direct/Pi-local or compact targeted sources where possible;
- if a Homey read is eventually unavoidable, batch/deduplicate it and store true source resolution;
- use Pi-side event derivation where practical instead of new Homey flows.

## Recommended preparation sequence

1. Keep current storage schema unchanged.
2. Register only genuinely new zone/CV metrics when the live source is known.
3. Add read-only source adapters on the Pi, one source at a time.
4. Backfill/collect passive data before adding any thermal planner logic.
5. Build a replay dataset containing naturally occurring Honeywell setpoint changes and corresponding Quatt/CV response.
6. Estimate per-zone `P(CV_ASSIST | deltaT, outsideTemp, ...)` and thermal response.
7. Only then add a `PURE_SHADOW` opportunity generator with `executeAllowed=false`.

## What is deliberately not prepared yet

- no Honeywell write adapter;
- no OpenTherm integration or manipulation;
- no Homey flow;
- no new systemd timer;
- no active planner code;
- no threshold for a "safe" setpoint delta;
- no assumption that all zones share the same thermal response;
- no authority/cutover change.

These omissions are intentional. The repository rule in `src/pi/README.md` requires accepted planner logic to be tested first in the active Pi runtime before synchronization back to GitHub.

## Next runtime investigation when appropriate

Without changing control, inspect on the Pi:

- live `ems-history.sqlite` metric/device registry;
- actual retention range and sample density;
- whether Honeywell zone temperature/setpoint history is already present under another device key;
- whether an authoritative CV-assist signal already exists from Quatt, Vaillant, gas data or a current compact state publication;
- whether direct Quatt telemetry can replace the remaining Homey Insights dependency later.

That investigation should be read-only and Pi-first; Homey should only be queried if a specific missing field cannot be resolved otherwise.
