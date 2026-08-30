# Homey EMS Core runtime source

This directory is the versioned source baseline and change staging area for the Homey Advanced Flow **EM v2 | 00 Core Tick**.

- Homey Advanced Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`
- Historical captured runtime: `core-v0.10.14.js`
- Current live Homey generation is newer than that historical capture; never deploy from `core-v0.10.14.js` as a full replacement.
- Safety: Core is SHADOW/read-only and must not perform physical device writes.

## Current live / prepared next change

Current live Homey Core observed on 2026-08-30:

`EM v2 | 00 Core Tick | v0.11c (Thermostat Verification)`

A natural run on 2026-08-30 exposed a v0.11c re-arm defect: `thermostatVerifyConsumedRunKey` is scoped to the complete physical boiler ON-run. Once one bounded verification episode is consumed, a materially later discretionary OFF during the same physical run can no longer start a new verification, even after the earlier stop condition cleared and the boiler continued confirmed heating.

Core v0.11d is now prepared in GitHub and is **not deployed to Homey**:

- `core-v0.11d-thermostat-verification-rearm.candidate.md` — edge-based verification episode/re-arm design.
- `smoke-v0.11d-thermostat-verification-rearm.md` — offline regression and later natural-cycle acceptance plan.

The v0.11d design retains the 20-minute hard bound but replaces the physical-run-wide consumed policy gate. Re-arm occurs only after the discretionary stop request has genuinely cleared (`true -> false`) for a normal Core tick while the boiler remains ON with confirmed >1500 W heating. A later new `false -> true` stop edge may then start exactly one fresh bounded verification. Continuously pending OFF conditions cannot renew verification windows.

Historical v0.11c preparation files remain for audit/history:

- `core-v0.11c-thermostat-verification.patch.md`
- `core-v0.11c-thermostat-verification.candidate.md`
- `smoke-v0.11c-thermostat-verification.md`

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
