# Pi Planner — current shadow policy

> **Current-state scope:** this document describes the Raspberry Pi 24h shadow planner that is published separately from the Homey planner. It is observability/planning only and performs no physical device writes.

## 1. Role

The Pi planner builds a 96 × 15-minute horizon from PV forecast, Quatt forecast, base-load forecast, warm-water plan and price context. The combined plan is written to `/home/jeroen/ems/data/shadow-load-plan.json` and translated for the website to `/home/jeroen/ems/data/energy-planner-shadow-pi.json`.

Current implementation:

- `src/pi/ems-runtime/planner/warm-water/build_ww_plan.py` — `EMS_PI_WW_PLAN_V0.6`;
- `src/pi/ems-runtime/planner/quarter-hour-plan/build_shadow_load_plan.py` — `EMS_PI_SHADOW_LOAD_PLAN_V0.6`;
- `src/pi/ems-runtime/planner/quarter-hour-plan/build_website_shadow.py` — `EMS_PI_ENERGY_PLAN_24H_V0.2` / `EMS_PI_PLANNER_SHADOW_PUBLISH_V0.2`.

The Pi planner remains **SHADOW/read-only**. Homey Core, gates and the Easee actuator remain responsible for realtime safety and physical EV control.

## 2. Tesla opportunity planning

Tesla support in Pi planner v0.6 is **opportunity-only**. Deadline planning is not yet included.

Opportunity charging does **not** require a requested kWh amount or target SoC. The planner asks only whether the Tesla is expected to be available and whether a forecast slot contains enough PV surplus to justify charging.

Electrical policy:

- 3-phase model: `690 W/A` (`3 × 230 V`);
- start threshold: `7 A` / `4830 W`;
- continuation threshold: `6 A` / `4140 W`;
- opportunity maximum: `16 A`;
- target current is rounded down to whole amps so forecast load does not intentionally exceed the available PV surplus.

A slot with sufficient predicted surplus receives `evPlanW > 0`, `tesla = RUN` and allocation reason `PV_EXPORT_OPPORTUNITY` in the website shadow output.

## 3. Tesla availability forecast

The weekly pattern is a **forecast**, never a physical control gate.

Normal expected presence:

- Thursday from 18:00: expected home;
- Friday, Saturday and Sunday: expected home;
- Monday before 08:00: expected home;
- Monday from 08:00 through Thursday before 18:00: expected away.

This models the normal travel pattern in which the car leaves Monday morning and returns Thursday evening.

Live `connected=true` is authoritative only for the near-term current home window. In v0.6 it may override the weekly forecast for at most the first **2 hours** of the planning horizon. It must not make the car appear available for all future 96 slots.

The intended precedence for future development is:

1. actual/near-term connected state;
2. explicit Tesla deadline/charge requirement;
3. normal weekly availability forecast.

An explicit future deadline is expected to override the normal weekly forecast once deadline planning is implemented.

## 4. Interaction with PV and warm water

Opportunity charging is based on forecast PV surplus after non-controllable load. Warm-water planning is also represented in the combined flex plan. The combined output reports import/export before and after flex so double allocation or unintended grid import remains observable.

Opportunity charging is not intended to create discretionary grid import. If the planner produces additional import solely because of an opportunity allocation, that is a planning defect to investigate rather than intended policy.

### Warm-water policy v0.6 — contiguous PV windows, low start frequency, comfort guaranteed

The electric boiler is treated as a flexible thermal buffer whose first objective is to absorb local PV that would otherwise be exported, without creating unnecessary start/stop behaviour for small forecast fragments.

For every day in the 24-hour horizon where the warm-water goal has not already been reached:

- the nominal requirement remains 240 minutes / 7.6 kWh at 1.9 kW, with a local deadline of **19:00**;
- partial PV coverage remains useful; the planner does not require the full 1.9 kW boiler load to be covered by PV;
- the planner first detects **contiguous windows of positive forecast export** rather than scoring isolated 30-minute blocks independently;
- a PV-driven start is only justified when such a contiguous window contains at least **0.10 kWh** of forecast export energy and spans at least **30 minutes**;
- eligible PV windows are preferred by average useful PV coverage, with total captured PV as the secondary criterion. This means a strong afternoon export window naturally outranks a weaker morning window, independent of clock time;
- once a qualifying PV window is selected, the boiler remains planned on through that contiguous export window instead of repeatedly switching every 30 minutes. If the remaining daily warm-water requirement is shorter than the window, the strongest contiguous sub-run is selected;
- the minimum discretionary run remains **30 minutes** (two quarter-hours);
- normal pure-grid fallback is not planned before **16:00**;
- from 16:00 onward, any remaining requirement is scheduled so the 19:00 comfort deadline is met;
- if waiting until 16:00 would leave too few quarter-hours to finish before 19:00, the fallback window is extended earlier only as far as needed to preserve the deadline. This safety rule intentionally overrides the normal 16:00 boundary;
- if today's goal is already reached, no further mandatory warm-water run is planned for today.

The website output exposes selected slots through `wwTargetW=1900` / `warmWater=RUN`. Allocation reasons distinguish `PV_SURPLUS_FULL`, `PV_PARTIAL_OPTIMIZED`, `DEADLINE_FALLBACK` and `SAFETY_EARLY_FALLBACK`. All slots selected as part of a qualifying PV window remain labelled as PV-assisted, including low-coverage continuation quarters within that same contiguous run.

The planner payload exposes `minPvWindowEnergyKWh=0.10`, `pvWindowPolicy=CONTIGUOUS_POSITIVE_EXPORT` and the per-day count `eligiblePvWindows` so the active policy remains observable.

This remains shadow planning only; it does not alter Homey physical-control ownership.

## 5. Validation evidence — 2026-09-06 / 2026-09-07

The first Tesla v0.5 implementation incorrectly treated `connectedNow=true` as availability for the entire 24-hour horizon. This caused nine Tesla opportunity slots / 9.83 kWh to be planned for the following Monday despite the normal Monday departure pattern.

Tesla planner v0.6 limits the live connected override to two hours and then falls back to the weekly forecast. After deployment on Sunday 2026-09-06 at approximately 21:09 CEST, the planner reported:

```text
PASS: shadow load plan v0.6 built
Tesla opportunity kWh    : 0.0
Tesla opportunity slots  : 0
grid import before flex  : 5.3
grid import after flex   : 5.3
```

On 2026-09-07 the warm-water forecast for 2026-09-08 showed 0.47 kWh of forecast export spread mainly across a continuous morning period from approximately 08:45 through 11:45, with individual quarter-hour export values below 250 W. That evidence showed that fixed per-slot or fixed 30-minute average power thresholds can discard a useful continuous self-consumption opportunity. Warm-water v0.6 therefore evaluates export energy over the complete contiguous window instead.

The Homey planner may temporarily show different warm-water or Tesla windows because Homey and Pi do not yet use identical future-planning semantics. This difference is expected while Pi functionality is being validated in shadow mode.

## 6. Website forecast presentation — 2026-09-07

The Planner page adds a frontend-only interactive presentation layer through `docs/javascripts/planner-forecast-interactive-v1.0.0.js`. The planner JSON, allocation logic and physical-control behaviour are not changed.

Presentation rules:

- every Homey/Pi planner renders its **own** 96-slot / 24-hour axis, derived from that planner's first forecast slot; the UI no longer stretches both forecasts onto one shared min/max axis when their generation times differ;
- base load is rendered as a continuous grey line with a subtle filled area so low overnight loads remain visible next to multi-kW PV peaks;
- PV remains yellow, expected import is blue and expected export is green below the zero line;
- one genuine power scale is used for the whole chart; 0.5 kW and 1.0 kW reference lines are visual aids only and do not alter values;
- desktop pointer hover shows a vertical selection marker and exact quarter-hour values; touch devices use tap to pin/unpin the same detail card;
- the detail card reports local timestamp, base load, PV, import, export and net import/export from the published planner fields. Visual minimum sizes never replace the numeric source values.

The existing `Geplande tijdsvakken` section remains unchanged.

## 7. Open items

- Validate warm-water v0.6 against the 2026-09-08 horizon and confirm that the main continuous morning export window is absorbed as one planned run, while the very small isolated fragments remain ignored and the remaining requirement falls back toward 16:00–19:00.
- Validate the same logic on a future day with a strong afternoon export window and confirm that the stronger afternoon period receives priority over weaker earlier periods.
- Add explicit Tesla deadline planning as a separate mode with higher priority than opportunity planning.
- Validate a Thursday/Friday horizon where the weekly model predicts the Tesla to be home and confirm that PV opportunity slots appear.
- Continue comparing Homey planner and Pi planner outputs before any migration of physical control ownership.
- Refine PV forecasting with historical per-array/shading correction; optimistic PV forecasts directly affect EV and warm-water opportunity quality.

## 8. Documentation rule

For this project, every functional, architectural or operational change must update the relevant project documentation in the same change set. Code-only behavioural changes are not considered complete.
