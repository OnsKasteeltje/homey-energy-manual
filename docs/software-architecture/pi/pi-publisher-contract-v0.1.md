# Pi EMS Publisher Contract v0.1

Status: PREPARATION / SHADOW DESIGN

## Source baseline

The latest Publisher implementation currently captured in GitHub is `Publisher v1.0.9 HARD-GATE LOW-LOAD`. The active Homey runtime has since moved to `Publisher v1.0.11 SCHEDULED LOW-LOAD`; the exact v1.0.11 source is not yet present in GitHub. Therefore this contract captures the stable functional behavior from v1.0.9 and marks the v1.0.11 scheduler delta as a runtime-source capture prerequisite before production ownership transfer.

## Purpose

Publish the canonical public EMS state to `docs/data/energy-state-v2.json` while keeping publication strictly decoupled from control semantics.

The Pi implementation MUST NOT wake or influence Core, Planner, Power Intent, adapters, gates or actuators as a side effect of publication.

## Inputs

Required semantic inputs:
- `EM2_Public_State` equivalent canonical public state object.
- authoritative state revision for revision consistency check.

Operational inputs:
- last successful publish timestamp.
- last successfully published revision.
- publication credential/token supplied through Pi secrets configuration, never stored in repository state.

## v1.0.9 captured Homey input IDs

For migration mapping/reference only:

| Purpose | Homey Logic variable ID |
|---|---|
| public state | `b0d68d98-efdb-41e4-be72-3bd6bdcc19eb` |
| state | `8e1efbb0-7999-494c-9429-7d274afacd79` |
| GitHub token | `235cfe0f-5760-48b9-9349-a33be47d04d1` |
| last publish | `fc95dcad-55d5-4d21-be15-f565f0a9bac3` |
| last published revision | `c10ea01b-3dfc-4e04-bb27-2a56dfc636cd` |

The Pi must not depend on these IDs internally once canonical state ownership has moved to Pi.

## Scheduling contract

Target production cadence: scheduled low-load publication every 15 minutes.

The Pi scheduler is authoritative for publication cadence. It should not depend on `EM2_Public_State changed` event fan-out.

The publish function itself remains idempotent and revision-aware:
- minimum interval: 900 seconds;
- publish on changed revision when due;
- heartbeat publication when due even if revision did not change;
- never create a retry storm after HTTP/API errors.

## Validation before publish

1. Public state must exist and be an object.
2. Public state revision must be numeric/valid.
3. If a separate authoritative state revision is available, it must equal the public-state revision.
4. Credential must exist.
5. State must satisfy the public-state schema before external write.

A revision mismatch is a hard block, not a warning.

## Output payload metadata

Before publishing, add/update:
- `meta.generated_at`
- `meta.heartbeat_at`
- `meta.publisher_version`
- `meta.state_revision`
- `meta.publish_reason`
- `meta.min_publish_interval_sec = 900`

Publish reason is semantic (`REVISION_EVENT` or `HEARTBEAT_EVENT`) even when the scheduler itself is periodic.

## External side effect

Single intended external side effect:
- update `OnsKasteeltje/homey-energy-manual/docs/data/energy-state-v2.json` on `main`.

Current Homey implementation obtains the current file SHA and performs a GitHub Contents API PUT. On conflict (`409`/`422`) it performs at most one fresh-SHA retry. The Pi implementation may use an equivalent GitHub write mechanism, but must preserve bounded retry and idempotency semantics.

## Observability

Pi-native publisher state should include:
- last attempt timestamp/revision;
- last success timestamp/revision;
- status (`IDLE`, `PUBLISHING`, `OK`, `ERROR_*`);
- failure counter by class;
- duration/latency;
- publish reason;
- target commit/reference when available.

Homey diagnostic-variable writes are transitional only and are not part of the final Pi architecture.

## Failure policy

- Invalid/missing public state -> no write.
- Revision mismatch -> no write.
- Missing credential -> no write.
- GitHub GET/write failure -> record error, no unbounded retry.
- 409/422 conflict -> maximum one refresh-and-retry attempt per scheduled run.
- Publication failure MUST NOT affect control execution.

## SHADOW comparison

Before ownership transfer, run Homey Publisher and Pi Publisher logically in parallel without allowing the Pi to update the production file.

For each due cycle compare:
- state revision;
- payload excluding intentionally volatile timestamps/version fields;
- due/not-due decision;
- publish reason;
- schema validation result.

Pi SHADOW output should be persisted locally or to a non-production artifact only.

## Promotion gate

Production ownership can transfer to Pi only when:
- exact active `v1.0.11 SCHEDULED LOW-LOAD` Homey source/trigger semantics have been captured;
- Pi has completed at least one full 24h scheduled shadow window;
- no semantic payload mismatches remain;
- heartbeat/revision scheduling is correct;
- GitHub conflict/error behavior is proven bounded;
- no Pi publication action can trigger the control path.

Promotion sequence:

```text
Pi Publisher SHADOW PASS
        -> enable Pi production publisher
        -> verify one successful Pi publication
        -> disable Homey Publisher
        -> update Homey API/load map
```

Rollback: disable Pi publisher and re-enable the unchanged Homey Publisher baseline. Do not combine rollback with Core/Planner/Power Intent changes.

## Open prerequisite

Capture the exact active Homey `Publisher v1.0.11 SCHEDULED LOW-LOAD` source/configuration into GitHub before production migration. Until then this document is sufficient for implementation scaffolding and SHADOW development, but not for final equivalence sign-off.
