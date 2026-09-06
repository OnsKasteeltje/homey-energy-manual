# Pi Planner — current shadow policy

> **Current-state scope:** this document describes the Raspberry Pi 24h shadow planner that is published separately from the Homey planner. It is observability/planning only and performs no physical device writes.

## 1. Role

The Pi planner builds a 96 × 15-minute horizon from PV forecast, Quatt forecast, base-load forecast, warm-water plan and price context. The combined plan is written to `/home/jeroen/ems/data/shadow-load-plan.json` and translated for the website to `/home/jeroen/ems/data/energy-planner-shadow-pi.json`.

Current implementation:

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

## 5. Validation evidence — 2026-09-06

The first v0.5 implementation incorrectly treated `connectedNow=true` as availability for the entire 24-hour horizon. This caused nine Tesla opportunity slots / 9.83 kWh to be planned for the following Monday despite the normal Monday departure pattern.

v0.6 limits the live connected override to two hours and then falls back to the weekly forecast. After deployment on Sunday 2026-09-06 at approximately 21:09 CEST, the planner reported:

```text
PASS: shadow load plan v0.6 built
Tesla opportunity kWh    : 0.0
Tesla opportunity slots  : 0
grid import before flex  : 5.3
grid import after flex   : 5.3
```

The website shadow builder also reported `Tesla slots : 0`. This is the expected Sunday-evening → Monday-evening result when no explicit deadline is active.

The Homey planner may temporarily show a different Tesla window because Homey and Pi do not yet use identical future-availability semantics. This difference is expected while Pi functionality is being validated in shadow mode.

## 6. Open items

- Add explicit Tesla deadline planning as a separate mode with higher priority than opportunity planning.
- Validate a Thursday/Friday horizon where the weekly model predicts the Tesla to be home and confirm that PV opportunity slots appear.
- Continue comparing Homey planner and Pi planner outputs before any migration of physical control ownership.
- Refine PV forecasting with historical per-array/shading correction; optimistic PV forecasts directly affect EV opportunity quality.

## 7. Documentation rule

For this project, every functional, architectural or operational change must update the relevant project documentation in the same change set. Code-only behavioural changes are not considered complete.