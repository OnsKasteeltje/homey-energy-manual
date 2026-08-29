# Homey runtime-state correction — 2026-08-29

Purpose: correct stale ON/OFF assumptions in the canonical Homey API/load map during the throttling investigation. These findings come from targeted read-only `get_advanced_flow` calls and must be treated as the current runtime truth until the canonical load map is refreshed.

## Confirmed runtime states

| Flow | Flow ID | Runtime state | Broken | Current structural load |
|---|---|---:|---:|---:|
| EM v2 | 80 Validation | P1 Pre-EV Gate v0.2 | `557ed7e8-9efe-4173-bc06-8e629214e172` | OFF | false | 0 |
| EM v2 | 60 Adapter | EV Power v0.1 SHADOW | `953e9b18-3576-4557-b940-ed4a64eb2516` | OFF | false | 0 |
| EM v2 | 80 Validation | EV Power Adapter Gate v0.2 | `ec5e5d34-8205-4cf0-a661-7bf744feb6e0` | OFF | false | 0 |
| EM v2 | 60 Actuator | EV Power v0.2 LIVE OWNERSHIP | `fea23193-a03f-49dd-9780-7e72ee48747d` | OFF | false | 0 |

## Consequence for throttling analysis

The previously documented EV downstream cascade must **not** be counted as current runtime load while these flows remain disabled. The current active Power Intent flow can still execute, but its downstream P1 Gate / EV Adapter / EV Adapter Gate / EV Actuator chain contributes zero event-driven runtime load in the present baseline.

Therefore the earlier estimate of roughly 48 Logic enumerations/hour across Power Intent + P1 Gate + EV Adapter + EV Gate is stale for the present runtime state. Only the actually enabled contributors may be counted in the current baseline.

## Prepared low-load work

- P1 Pre-EV Gate: targeted-read redesign prepared; do not deploy while OFF merely for load reduction.
- EV Power Adapter: targeted-read redesign prepared; ID binding pending; do not deploy while OFF merely for load reduction.
- EV Adapter Gate: still uses one full `getVariables()` when enabled; candidate for targeted reads before future re-enable.
- EV Actuator: still uses one full `getVariables()` when enabled. Because this is safety-critical LIVE-capable code, optimize only under a separate controlled change with explicit regression/safety validation.

## Investigation rule

Do not re-enable any of these EV downstream flows during the clean throttling baseline merely to test optimizations. Continue identifying the next **actually enabled** high-frequency flow with broad Logic/device enumeration.
