# Homey EMS 24h Planner runtime source

This directory is the versioned source baseline for the Homey Advanced Flow **EM v2 | 45 Planner | 24h Energy Plan**.

- Homey Advanced Flow ID: `27617767-0a64-43a3-9bcb-e34b0dd6a5c0`
- Last captured runtime baseline: `energy-plan-24h-v0.4.4.js`
- Previous source candidates: `energy-plan-24h-v0.4.5.js`, `energy-plan-24h-v0.4.6.js`
- Current source candidate: `energy-plan-24h-v0.4.7.js`
- Schedule in Homey: every 15 minutes with a 45-second stagger; manual start path is also present.
- Safety: SHADOW/read-only; no Victron, Easee, boiler, or other physical device writes.

## v0.4.5 base-load hardening

v0.4.5 prevents sparse history from turning a high unexplained global median into a fictitious all-night base-load forecast.

- Tesla and boiler power remain subtracted from house power before base learning.
- Samples marked washer-active or dryer-active are excluded from base learning.
- Residual base samples at or above the existing `HIGH_LOAD_UNIDENTIFIED` threshold of 1500 W are excluded from base learning.
- A quarter-bin forecast requires at least two clean samples for that local quarter.
- A global clean fallback requires at least three clean samples and must remain below 1500 W.
- If neither condition is met, `baseLoadForecastW` stays `null` and quality becomes `INSUFFICIENT_CLEAN_BASE_HISTORY`; the planner does not invent a high fallback.
- This remains SHADOW-only and cannot perform physical writes.

## v0.4.6 Tesla PV opportunity hardening

v0.4.6 separates physical Tesla start requirements from runtime anti-flapping and prevents isolated 15-minute forecast opportunities.

- A new opportunity run may start only when forecast `pvSurplusBeforeFlexW >= 4830 W`, corresponding approximately to the required 3-phase 7 A Tesla/Easee start bump.
- Once a forecast run has started, it may continue while `pvSurplusBeforeFlexW >= 4140 W`, corresponding approximately to 3-phase 6 A.
- A forecast opportunity must contain at least 2 consecutive 15-minute slots (30 minutes).
- The existing runtime 115/120-second confirmation remains a separate actuator-layer anti-flapping safeguard; planner minimum-run logic does not replace it.
- Opportunity planning remains PV-only and cannot be triggered by a cheap or negative price when no Tesla deadline is active.
- Planner output publishes `opportunityStartMinW`, `opportunityContinueMinW`, `opportunityMinRunSlots`, `opportunityMinRunMinutes`, and `pvOpportunityRuns` for traceability.
- This remains SHADOW-only and cannot perform physical writes.

## v0.4.7 warm-water day-boundary planning

v0.4.7 makes warm-water planning explicitly aware of the Europe/Amsterdam calendar day.

- `goalReachedToday` and `remainingFallbackMin` apply only to the current local day and no longer suppress warm-water planning after midnight.
- Every future local day represented in the 24-hour horizon starts with the configured daily fallback of 240 minutes until runtime evidence for that day can replace it.
- Each local day gets its own 19:00 deadline and its own WW allocation.
- WW allocation remains PV-first; within equal PV coverage a DYNAMIC contract may use price as a tie-breaker.
- Current-day catch-up state is never copied into a future day.
- Planner output publishes `dayBoundaryAware`, `horizonDates`, `dailyPlans`, `currentDay`, and `futureDays` for traceability.
- The implementation remains SHADOW/read-only and performs no boiler or other actuator writes.

## Inputs and outputs

The planner reads the current EMS state, warm-water state, contract/price context, day history and PBTH price buffer. It also retrieves a 15-minute shortwave-radiation forecast for Hauwert from Open-Meteo.

It writes only the canonical planner snapshot Logic state consumed by the Planner Shadow publisher.

## Migration and change rule

GitHub is the source-of-truth for planner code. Never reconstruct or simplify the HomeyScript while deploying a change: start from the latest captured baseline, make the smallest reviewable diff, preserve SHADOW safety, and smoke-test the relevant chain before migrating the next flow.

**Migration gate:** one flow migration = one change-set = one chain smoke test = PASS before the next migration.
