# PV daily accounting integrity — 2026-10-12

## Scope / authority
Read-only correction of `ems-performance` day KPI provenance.
**No change** to Pi planner, Homey, EV executor, PV decisions, EV constrained replay,
control endpoints, live EV thresholds, or publishing.

### Evidence: 2026-10-11 (Europe/Amsterdam)
- PV & Flex historical energy intervals: 19.488001 kWh PV, 4.677998 kWh P1
  export, 13.252004 kWh P1 import, derived PV self-consumption 14.810003 kWh
  / 19.488001 = **76.0%** (rounded to one decimal).
- `ems-performance` previously integrated 18.115 kWh sampled inverter power,
  4.437 kWh sampled P1 export, and 14.567 kWh of clamped direct use, showing
  **80.41%**. These are **different data paths**, not interchangeable KPIs.
- Thirteen five-minute snapshots had P1 export greater than simultaneously
  archived inverter power. The sum of that impossibility was **0.890 kWh**.
  Examples: 13:50 local 3,930 W export against 1,451 W inverter sum;
  16:10 local 3,824 W against 1,550 W.
- Three consecutive identical SolarEdge power values despite abrupt P1 changes
  suggest stale/held/timestamp-misaligned source snapshots. Source cause is
  **not proven**. `quality=observed` with 300 s resolution does not prove freshness.

## Implementation
- The **authoritative daily PV KPI** comes from the existing
  `house_energy_intervals` (archived meter-energy deltas), using P1 for
  import/export. Daily PV self-consumption is *PV energy - P1 export energy*.
  It is a derived balance, not directly measured PV-to-appliance energy.
- Require at least **95% paired P1/PV coverage** over the elapsed Amsterdam
  calendar day. Reject negative day energy balance. Without that coverage,
  `metrics.pv_self_consumption_rate` and
  `metrics.direct_pv_self_use_kwh` are `null`, not invented.
- Existing `metrics` keys remain present. Daily PV/grid/house KPI values
  are promoted from archived energy intervals when coverage qualifies.
  `sampledPowerMetrics` retains the original integrated-power calculation
  for diagnostics and flex analysis.
- `powerSampleQuality` reports impossible instantaneous PV/P1 export
  intervals (count, energy and review flag). This is **not** extra missed EV
  capture. Neither P1 telemetry nor the EV control loop is adjusted.
- The `benchmark` and EV/boiler PV attribution remain explicitly
  *sampled-power, unconstrained/derived* and must not be labelled measured
  or used as proof of an EV fault.
- Read-only day report source: `services/pi/history/ems_performance.py`.

## Validation
```bash
python3 tests/replay/test_ems_performance.py
python3 tests/replay/test_ems_performance_energy_accounting.py
python3 tests/replay/test_constrained_replay_v0_1.py
bash scripts/ems_architecture_gate.sh
git diff --check
```

Synthetic 11 October test fixtures model the disclosed day totals and the
reported 13 sample anomalies, not byte-for-byte raw historical data.

After a controlled Pi pull and deploy, compare:
```bash
ems-performance 2026-10-11 | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["metrics"]["pv_self_consumption_rate"], d["energyAccounting"]["status"], d["powerSampleQuality"])'
```

Expected if underlying archive remains unchanged: ratio `0.76`, energy
accounting `GOOD`, 13 impossible-export intervals and ~0.890 kWh.
Check against `/web/analysis/pv-flex/day/2026-10-11` separately.

## Non-goals
No Tesla/EV charging changes; no automatic backfill or database writes; no
changes to Constrained Replay or its `EV_EXPORT_ONLY` scope; no Homey
publisher; no heating or Quooker physical actuation; no frontend deployment
in this patch.
