# Core v0.11d — live deployment precheck

Status: **PASS — READ-ONLY PRECHECK / NO HOMEY MUTATION**

Date: 2026-08-30

Live Homey flow inspected read-only:

- Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`
- Name: `EM v2 | 00 Core Tick | v0.11c (Thermostat Verification)`
- Enabled: `true`
- Broken: `false`
- Trigger cadence: every 5 minutes
- Core publisher version: `EM2_CORE_STATE_V0.11c`
- Core remains read-only with no physical device writes

## Baseline confirmation

The live v0.11c script still contains the known run-wide thermostat verification latch:

- `prevVerifyConsumedRunKey`
- `thermostatVerifyConsumed`
- `thermostatVerifyConsumedRunKeyOut`
- eligibility gated by `!thermostatVerifyConsumed`

The live script therefore still matches the defect model addressed by the prepared v0.11d re-arm delta.

The current WW verification branch ordering also matches the prepared patch assumptions:

1. mandatory mode / 19:00 / goal / catch-up branches remain above thermostat verification;
2. normal run-lock remains above thermostat verification;
3. thermostat verification abort / expiry / active verification remain immediately before discretionary planner/import/price OFF branches;
4. downstream Power Intent / WW Adapter / Gate / actuator ownership is unchanged.

## Pre-deployment compatibility check

PASS conditions confirmed:

- live baseline is exactly v0.11c thermostat-verification generation;
- flow is enabled and not broken;
- cadence remains 5 minutes;
- `PUB_VERSION` is still v0.11c;
- the defect-causing consumed-run latch is still present;
- prepared v0.11d patch targets the same variables and branch location;
- no evidence of a newer Core WW implementation invalidating the patch assumptions;
- no Homey write was performed during this precheck.

## Prepared deployment unit

Apply only `core-v0.11d-thermostat-verification-rearm.patch.md` to this exact live v0.11c script.

Expected intentional changes only:

1. version/name/note metadata;
2. remove run-wide consumed latch as a policy gate;
3. add stop-request edge tracking;
4. add bounded verification episode state;
5. add genuine clear -> re-arm -> later false-to-true OFF-edge behavior;
6. preserve 20-minute hard limit and all existing MUST/safety precedence;
7. add associated WW control observability fields.

No change is allowed to device IDs, 5-minute cadence, Planner v0.4.9 semantics, Tesla logic, Quatt observe-only behavior, Publisher cadence, Power Intent ownership, WW Adapter/Gate/Actuator ownership, 19:00 stop, or Core's no-device-write rule.

## Gate result

**LIVE BASELINE PRECHECK: PASS**

The prepared v0.11d delta is compatible with the currently live v0.11c Core generation. Offline regression A-J remains the required functional gate before deployment, followed by exactly one Advanced Flow update and natural-cycle validation.
