# Supporting Homey flows — grouped runtime source capture — 2026-08-30

This capture was read directly from Homey on 2026-08-30 and records the current runtime identity/state for the supporting EMS flows. It is a source-capture baseline only: no Homey flow was started, enabled, disabled, or modified during capture.

| Flow ID | Runtime name | Enabled | Broken | Trigger contract |
|---|---|---:|---:|---|
| `8526109f-5c8d-428e-ac24-85a71c95ac36` | `EM v2 | 05 Watchdog | Core + Publish Freshness v0.3.3 staggered` | false | false | every 5 min + 120 s delay |
| `a41079f7-2287-4ec0-9e9b-27619e93ba35` | `EM v2 | 06 Freshness | Day-Night Normalizer v0.1.1` | false | false | every 5 min + 30 s delay; day/night branch |
| `1d822642-87e8-4b0f-870e-5f2e7eef9372` | `EM v2 | 70 Planner | WW Scheduling SHADOW v0.2` | true | false | programmatic trigger only |
| `5538f1c9-9a21-4328-9896-942952f5c55f` | `EM v2 | 50 Decision | WW Post-Goal Opportunity v0.4 SHADOW` | true | false | every 15 min + manual start |
| `543664be-d07a-4099-92d1-07878b73215d` | `EM v2 | 50 Decision | WW Seasonal Source Advisor v0.3 SHADOW idempotent` | true | false | daily 20:30 + manual start |
| `df295b26-9a47-497a-87c7-ccfd32323db1` | `EM v2 | 70 History | Control Audit v0.4 low-load` | false | false | `EM2_Control_WW` changed + 2 s settle |
| `14027232-905e-4b8b-828d-5b44b8f6692e` | `EM v2 | 70 History | Day Series v0.6.1 TARGETED LOCAL SAMPLER` | false | false | every 5 min + manual start |
| `322bcfe6-1ec4-46d4-a840-d13009d9c9c9` | `EM v2 | 72 History | Immutable Day Archive v0.1` | false | false | every 60 min + manual start |
| `9aba3344-b8b4-423f-9132-b606990b9ffe` | `EM v2 | 76 Evidence | BC Planner Intent Recorder v0.4 local-first` | false | false | every 15 min + manual start |
| `9193b3ae-1e3d-4b52-aa95-60aff099e68a` | `EM v2 | 05 Config | EMS Settings Sync v0.3 low-load` | false | false | every 5 min + manual start |

## Important runtime observations

- The Watchdog flow is currently **disabled** and still contains display/note references to older Core/Publisher names (`v0.10.12` and `v1.0.4`) while its programmatic trigger IDs point at the current Core and Publisher flow IDs. This is captured as-is; no silent runtime correction was made.
- The Day-Night Normalizer, Control Audit, Day Series, Immutable Day Archive, BC Planner Intent Recorder, and EMS Settings Sync are currently **disabled**.
- WW Scheduling SHADOW v0.2, WW Post-Goal Opportunity v0.4 SHADOW, and WW Seasonal Source Advisor v0.3 are currently **enabled**.
- The WW Scheduling note says “Disabled pending code/runtime validation”, but Homey runtime reports `enabled=true`; runtime state wins and the textual note is therefore stale.
- This capture intentionally excludes `[ROLLBACK]`, `[FAILED-DIRECT-API]`, `[RETIRED DUPLICATE]`, TEMP/ONE-SHOT/DONE flows and superseded Tesla controllers from the active source-of-truth.

## Source ownership rule

For these flows, Homey runtime is the observed deployed implementation. GitHub stores the source-managed baseline. A future runtime change is not considered source-managed until this capture/source is updated and, where relevant, smoke-tested.
