# Heating gas winter analysis V0.1 — read-only pilot

Status: **offline winter retrospective not scheduled**; separate P1 gas/Quatt CV live read-only telemetry **commissioned 15 October 2026**. Historical Analysis perspective; no control authority. Baseline: 2025-11-01 to 2026-04-01 (Europe/Amsterdam).

## Goal and evidence

Identify **hypotheses** for improving Honeywell heating schedules to reduce gas use without sacrificing comfort or increasing total energy cost. P1 gas is the authoritative **whole-house cumulative gas meter**, not room heating gas. Domestic hot water via CV is a confounder. Daily weather uses Homey weather Insights (avoids possible solar bias in the Quatt outside sensor). Quatt `cvActive` is not proof of gas flame; `cv_flame` has no established reliable winter history. Historical Honeywell weekly schedules must not be used to invent historical effective targets or overrides.

Source: existing Homey Insights, via the already installed Pi Homey CLI path/identity used in `src/pi/ems-runtime/datastore/collect_homey_insights.py`. No second recurring collector, Homey flows or private GitHub data. `services/pi/history/winter_heating_gas_v0_1.py` performs explicit one-off *read* calls and stores its snapshot outside the repository, locally in `/home/jeroen/ems/data/analysis/`, permission 0600. It never mutates `ems-history.sqlite`. Output is retrospective and **does not enter the dynamic planner**.

The historic `lastYear`/`thisYear` Insights layers expose approximately six-hour **aggregated** samples, including averages of cumulative gas counters. Their differences give **approximate** gas consumption assigned to the ending local day; they are not meter-register boundary readings. No six-hour gap, reset, missing/null value, DST anomaly or unavailable evidence may be silently interpolated. A daily row requires 4 gas intervals and 4 outside-temperature samples. The DST transition day should be separately reviewed before relying on its daily amount. The calculation `max(0,18 °C − outside mean)` is an indicative heating-degree-day proxy, not a physical gas attribution. Six-hour room target/actual averages do not reveal the exact time of switching or short boiler assistance.

## One-off usage (only on Pi after inspecting existing production load)

```bash
cd /home/jeroen/ems/repo/homey-energy-manual
# Initial pilot: January–March 2026, two rooms, bounded sequential Insights reads.
python3 services/pi/history/winter_heating_gas_v0_1.py --collect --years 2026 \
  --rooms woonkamer,eetkamer --start 2026-01-01 --end 2026-04-01

# Offline report: ZERO Homey requests.
python3 services/pi/history/winter_heating_gas_v0_1.py \
  --start 2026-01-01 --end 2026-04-01

# Optional later, by explicit decision: add 2025 and/or other rooms.
# python3 ... --collect --years 2025,2026 --rooms woonkamer,eetkamer,keuken,serre,douwe_slaapkamer,erker_douwe
```

The export skips already successfully fetched metric/year pairs (resumable). It inserts an 8-second delay between calls. On 429 or any unexpected error it stops immediately, without retry; run only after Homey production traffic is healthy. No automatic scheduling. Do not commit/export the local evidence JSON, account data, household setpoint history, or secrets to GitHub.

## Interpretation / next gate

1. Check coverage and season-to-season comparability first. Winter 2025 metrics may contain null values. Don't backfill history from today's Honeywell schedule.
2. Compare daily/weekly gas versus outdoor temperature and Quatt delivered heat **as correlation**, not causation; control for weather, occupancy and CV tapwater.
3. Use target-versus-actual as a comfort/under-target indicator, **not a room gas meter**.
4. **Do not issue saving percentages, prescribe exact room changes or claim cv assist** until DHW/space-heating distinction and targeted higher-resolution trials are available.
5. Any subsequent setpoint change needs separate comfort-policy approval and a bounded, reversible experiment. Honeywell remains authority; Homey remains writer; shadow/analysis performs no device writes.

## Acceptance

Only two focused offline retrospective tests: a complete six-hour counter day and a missing-bucket case. No GitHub workflow, timer, frontend route or automatic Insights collector was added. The historical analyzer remains a one-off tool; the separate live gas/CV telemetry was later commissioned through the existing Homey→Pi ingest, with two additional targeted archive tests.


## Live-season gas/CV observations (read-only; commissioned)

The existing Core v0.11p already reads the P1 and Quatt devices in its single targeted acquisition batch. Release `5e386b717` adds one additive schema-2.13 observation:

- `grid.gas_meter_m3` from the **existing** P1 `meter_gas` capability; absent/non-finite/negative is `null`. The new `grid.gas_meter_sample_at` carries this capability's independent `lastUpdated` timestamp. This is the whole-house **cumulative** gas meter, not gas-use power and not space-heating-only energy.
- Existing `quatt.cv_requested` is preserved as **nullable raw boolean** from `measure_boiler_cic_central_heating_on`, rather than coercing an unavailable capability to `false`.
- Existing `quatt.cv_flame` remains nullable. `cv_requested` (call for assistance) and `cv_flame` (potential observed burner signal) remain different facts; `cvActive` (boiler operating mode) is not burner proof.

`services/pi/api/status/history_archive.py` archives observations from the **already accepted Core push** in the existing `ems-history.sqlite` registry:

| Device | Metric | Type | Source |
|---|---|---|---|
| `grid_p1` | `gas_meter_m3` | cumulative m³ | `grid.gas_meter_m3`, with the independent `grid.gas_meter_sample_at` timestamp; only valid P1 observations; absent/invalid timestamp is skipped |
| `quatt_cic` | `cv_requested` | boolean | `quatt.cv_requested`, only when actual boolean |
| `quatt_cic` | `cv_flame` | boolean | `quatt.cv_flame`, only when actual boolean |

Existing P1/Quatt power and CV snapshots keep the Core sample timestamp. Gas counters are different: the meter capability can update later than electrical P1, so each gas observation uses its **own** `lastUpdated` instant, not the Core power tick. Missing, malformed or future-dated capability timestamps cause the gas row to be skipped. Gas source resolution is stored as unknown (`NULL`) rather than falsely claiming every five minutes. Thus repeated Core publishes of an unchanged gas capability timestamp remain idempotent. Archive best-effort behavior, single-reader Homey source and control authority do not change. In particular, **null CV burner does not mean off**. A gas counter is never treated as a direct meter of central-heating energy. Consecutive meters with gaps, counter resets, or `held` quality must not be naively differenced.

**Warm water mode is already archived** as an observed semantic event in `services/pi/history/archive_semantic_events.py` (`warm_water.source_mode` and `WW_SOURCE_CHANGED`). The initial observation is a baseline, not an invented historical transition. We deliberately do not duplicate it as a new high-frequency measurement.

### Live commissioning confirmation — 2026-10-15

The Pi targeted status-API archive update returned PASS with a bounded HTTP readiness check after an initial premature health probe had rolled back safely. The exact Homey Core v0.11p code was reconciled against the previous pinned live script and installed in the **existing** enabled flow. Homey and SQLite readback confirmed the independently timestamped gas counter and two sequential observed CV-request false rows; burner activity remained `null`, with no fabricated `cv_flame` row. A normal five-minute cadence must not be inferred from gas meter data. The original full-deployment marker remains older because this was a scoped file install. Neither the winter retrospective analyzer nor the new telemetry invokes heating controls. No schema major/minor bump, second publisher, new Homey flow, Homey Insights reader, physical writer, or scheduled job was introduced.

Minimal targeted regression test:

```bash
python3 -m pytest -q tests/integrations/test_history_archive_counters.py
```

After commissioning, verify continued ingestion through the accepted `/state/energy` path: recent SQLite `grid_p1/gas_meter_m3` and `quatt_cic/cv_requested` rows must have honest timestamps and quality, and there must be no `cv_flame` row until the source provides a real boolean. Existing `warm_water.source_mode` remains separate semantic event state. The full Pi deployment marker was intentionally not rewritten by the targeted archive installation; running an unqualified full Pi deploy could inadvertently promote unrelated code. Keep all temperature changes shadow-only.

## CiC supervisory-control mode — read-only collector (candidate, not yet deployed)

The 16 October 2026 Douwe bedroom test physically confirmed boiler operation
while the Homey `quatt.cv_requested` signal stayed false. The P1 gas counter
increased, but `cv_flame` was unavailable. These are observations, not proof
that the P1 meter alone can attribute gas use to space heating.

The local Quatt CiC feed `/beta/feed/data.json` exposes
`qc.supervisoryControlMode`: `0` standby, `1` standby/heating,
`2` heat pump only, `3` heat pump + boiler, `4` boiler only; additional
maintenance/protection values must be preserved as observed, not mapped to
standby. Modes 3/4 indicate **CiC-selected boiler operation**, not independently
confirmed gas flame. Verify correlations against real gas counter updates,
hot-water source and, where possible, physical burner observation before
using mode for heating optimisation or safety decisions.

The proposed `services/pi/integrations/quatt/collect_quatt_cic_mode.py`
uses **only one local HTTP GET each minute**, separate from the existing
five-minute Homey Quatt collector. It inserts `quatt_cic /
supervisory_control_mode` in the existing `ems-history.sqlite` with actual
UTC observation timestamp, `quality=observed`, and
`source_resolution_seconds=60`. Invalid/missing/unknown-source payloads
fail closed (no fabricated standby). Failures cannot affect the Homey or
heating control chain; the one-minute timer does not replay missed samples.

Pi-local configuration: `/etc/default/ems-quatt-cic-mode` contains
`QUATT_CIC_URL=http://<private-CiC-IP>:8080/beta/feed/data.json`; this
machine-specific address must not be embedded in public source. New
`ems-quatt-cic-mode.service/.timer` are **not** activated by merely merging
this source. Commission the timer explicitly after a clean read-only trial
and a successful test. No Homey flow, planner priority, CV guard, actuator,
Honeywell target, or physical write changes. The mode remains ANALYSIS ONLY.
