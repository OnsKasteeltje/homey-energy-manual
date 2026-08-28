# EM v2 Publisher

## Homey runtime

- Flow ID: `fe84bc17-72d4-4fbb-9a69-b3d751b0ffcd`
- v1.0.5 topology: Start -> 90 s delay -> standalone HomeyScript `EM v2 - Publish ShadowData`
- Standalone script ID: `83a93b0f-4ca5-49c9-8c43-03c24e3d9b1d`
- The standalone script source is not exposed by the current Homey connector and is therefore intentionally left unchanged in v1.0.6.

## v1.0.6 instrumentation

Purpose: isolate the stale-publication failure without changing physical control or replacing the existing GitHub writer.

Topology:

`Start -> 90 s delay -> preflight -> Publish ShadowData -> success diagnostic`

Both the preflight error path and the Publish ShadowData error path end in the error diagnostic action.

The added inline HomeyScript actions only enumerate Logic variables and write diagnostic Logic variables. They perform no device writes.

### Diagnostic variables

- `EM2_Publisher_Flow_Diag_Code`
- `EM2_Publisher_Flow_LastAttemptRevision`
- `EM2_Publisher_Script_Diag_Mirror`

### Flow diagnostic codes

| Code | Meaning |
| ---: | --- |
| 110 | `EM2_Public_State` missing or invalid JSON |
| 111 | Public State revision missing or invalid |
| 112 | `EM2_State` missing or invalid JSON |
| 113 | Public State and Core State revisions do not match |
| 120 | Preflight ready; existing Publish ShadowData action may run |
| 200 | Existing Publish ShadowData action card returned success |
| 510 | Existing Publish ShadowData action card returned error |

A code `200` means only that Homey's action card returned success. It does **not** prove that `docs/data/energy-state-v2.json` changed. That is verified separately against GitHub. `EM2_Publisher_Script_Diag_Mirror` captures the existing `EM2_Publisher_Diag_Code` so an internally handled failure remains visible even when the action card itself reports success.

## Safety

Publisher v1.0.6 is publication/diagnostic infrastructure only. It must not perform boiler, EV, Quatt or other physical actuator writes.
