# Core v0.10.16 runtime-sync smoke

Date: 2026-08-28

Result: **PASS**

Change-set under test: `core-v0.10.16-runtime.patch.md` (runtime reconstruction capture of active Homey Core v0.10.16).

## Targeted chain

`manual Core start -> semantic Logic outputs -> Publisher diagnostic -> public state revision`

## Observations

- Homey flow `EM v2 | 00 Core Tick | v0.10.16 (safe semantic fan-out)` started successfully through its manual start path.
- Existing diagnostic flow `EM v2 | 40 Data | Publisher Probe v0.1 (Logic snapshot)` was run once after the Core start. It performs one Logic enumeration and no physical device reads/writes.
- Latest diagnostic snapshot name: `TEMP_PUBDIAG_F210_M22_A2997_L210_P2997`.
  - publisher last-attempt revision: `2997`
  - last-published revision: `2997`
- Public `docs/data/energy-state-v2.json` also reported state/decision/shadow revision `2997`.
- The manual Core run did not create a new semantic revision. That is the expected result when only volatile/freshness data changes under v0.10.16 semantic fan-out suppression.
- No Homey rate-limit was observed during this controlled smoke.
- Core remains SHADOW/read-only and no physical actuator write is part of the Core code path.

## Gate

**PASS** — the runtime-sync change-set is accepted. Further Core/Planner low-load preparation may proceed.
