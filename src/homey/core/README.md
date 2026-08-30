# Homey EMS Core runtime source

This directory is the versioned source baseline and change staging area for the Homey Advanced Flow **EM v2 | 00 Core Tick**.

- Homey Advanced Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`
- Historical captured runtime: `core-v0.10.14.js`
- Current live Homey generation is newer than that historical capture; never deploy from `core-v0.10.14.js` as a full replacement.
- Safety: Core is SHADOW/read-only and must not perform physical device writes.

## Prepared next change

Core v0.11c thermostat verification is prepared in GitHub but is **not deployed to Homey**:

- `core-v0.11c-thermostat-verification.patch.md` — exact bounded-control design and deployment delta.
- `smoke-v0.11c-thermostat-verification.md` — natural-cycle smoke/acceptance plan.

The v0.11c design keeps one authoritative `EM2_Control_WW` decision/write. It must not publish a transient `BOILER_OFF` and correct it afterwards. Thermostat verification is bounded to 20 minutes and cannot override MUST-OFF, 19:00, stale/invalid P1 or unsafe import conditions.

## Change rule

Never reconstruct or simplify the Core script while deploying a change. Start from the **complete current live flow**, make the smallest reviewable diff, validate that all existing functional sections are retained, and only then deploy the complete script to the existing Advanced Flow.

Before any Core Homey mutation:

1. capture/fetch the complete live Advanced Flow;
2. preserve it as the rollback unit;
3. apply only the reviewed patch to that complete runtime;
4. compare the resulting full script against the captured live baseline;
5. perform one Advanced Flow update only;
6. smoke only when Homey is not rate-limited.

For fan-out optimisation, timestamps/heartbeat metadata must not create downstream Logic change events when the semantic state or control intent is unchanged. Public-state publication freshness is transport metadata and must not be used as an internal control trigger.
