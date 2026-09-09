# Dynamic Pi Planner — PURE_SHADOW v0.1

The Dynamic Pi Planner is an experimental rolling 24-hour optimizer that runs beside the current WW and quarter-hour planners. It must not perform physical writes.

## Objective

Maximize expected PV self-consumption while preserving hard comfort and safety constraints.

The key design rule is that WW has a hard comfort objective, not a fixed time priority. The optimizer may therefore use WW on PV flanks, pause it during a high PV peak so a connected Tesla can absorb that peak efficiently, and resume WW later, as long as the remaining WW requirement can still be met before the 19:00 deadline.

## Dynamic PV allocation

There is no fixed PV start threshold such as 500 W. A slot is valued relative to the remaining horizon. Lower actual export can be valuable when it is one of the best remaining WW opportunities; higher export can be intentionally left for Tesla when the EV can absorb the peak and WW remains feasible elsewhere.

Forecast export is corrected in the near horizon with live P1 export. The live influence is strongest now and decays smoothly over two hours.

## Forecast confidence

Confidence is intentionally compact and uses only three signals:

1. forecast consistency between consecutive planner runs;
2. cloud stability around the slot;
3. recent local PV forecast accuracy against measured site PV.

Forecast horizon is only a mild prior (maximum 8% reduction over 24 hours), so a stable clear-sky day can retain high confidence across the full rolling horizon.

The confidence state stores only the previous 24-hour PV forecast and one smoothed local-accuracy value. No large meteorological parameter history is required.

## Guardrails

- `mode = PURE_SHADOW`
- `readOnly = true`
- `control_writes = false`
- WW comfort/deadline remains the primary hard objective.
- Tesla is a secondary flexible load and may use peak PV only when WW feasibility is preserved.
- Existing WW and quarter-hour planners remain unchanged and provide the comparison baseline.
- Before any future control use, replay validation must prove comfort feasibility, minimum-run behaviour, PV capture improvement, and bounded extra grid import.

## Daily PV-capture validation

`validate_pv_capture.py` evaluates each completed local day from the control-independent 5-minute measurement history in `ems-history.sqlite`. It is analysis-only and never writes to Homey or a physical device.

It publishes these primary KPIs:

- `pvSelfConsumptionRate`: measured PV used directly in the house divided by measured PV production;
- `flexiblePvCaptureRate`: PV absorbed by Tesla + boiler divided by the counterfactual pre-flex export (`measured export + PV-fed flexible load`);
- `batteryRelevantResidualExportKWh`: measured export remaining after all actual household and flexible-load consumption. This is the starting point for battery ROI analysis.

The validator also records Tesla and boiler PV capture separately, input coverage, and the exact calculation method. Results are retained for 90 days in `/home/jeroen/ems/data/pv-capture-history.json` and the latest completed day in `/home/jeroen/ems/data/pv-capture-validation.json`.

`ems-pv-capture-validation.timer` runs daily at 00:20 and publishes both JSON files to `docs/data/` for website/review use.

## Output

Runtime output:

`/home/jeroen/ems/data/dynamic-shadow-plan.json`

Persistent compact confidence state:

`/home/jeroen/ems/data/dynamic-confidence-state.json`

The systemd PV forecast cycle invokes the Dynamic Planner after the existing shadow load plan has been built. This gives all three models the same forecast refresh cadence for later A/B comparison.
