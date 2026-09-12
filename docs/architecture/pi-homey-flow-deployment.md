# Pi → Homey Advanced Flow Deployment

Status: VALIDATED + ACTIVE CUTOVER ARCHITECTURE
Updated: 2026-09-12

## Purpose

EMS Advanced Flow changes can be prepared and deployed from the Raspberry Pi instead of manually copying code through the Homey web interface.

This remains a deployment mechanism. Planner authority is controlled separately by the Homey Logic selector `EM2_Planner_Authority`.

## Deployment architecture

```text
GitHub / local candidate
        |
        v
Raspberry Pi
        |
        +-- targeted live read
        +-- pre-deploy backup
        +-- canonical diff / SHA-256
        +-- writable-only payload
        +-- explicit apply
        +-- Homey update
        +-- targeted read-back
        +-- SHA-256 verification
        +-- rollback path
        |
        v
Homey Advanced Flow
```

## Pi locations

Read-only auditor:

`/home/jeroen/ems/runtime/homey-deploy/homey_flow_audit.py`

Controlled deployer:

`/home/jeroen/ems/runtime/homey-deploy/homey_flow_deploy.py`

Backups:

`/home/jeroen/ems/backups/homey-flows/`

Homey CLI project:

`/home/jeroen/ems-homey-adapter`

Homey CLI:

`/home/jeroen/ems-homey-adapter/node_modules/.bin/homey`

Node runtime:

`/opt/node-v24.20.0/bin`

## Homey Advanced Flow interface

Targeted read:

```text
homey api flow get-advanced-flow --id <FLOW_ID> --json
```

Controlled update:

```text
homey api flow update-advanced-flow \
  --id <FLOW_ID> \
  --body @<PAYLOAD_FILE> \
  --json
```

Only these Advanced Flow fields are sent in an update payload:

- name;
- enabled;
- cards.

Read-only response metadata such as the following must not be sent back:

- id;
- broken;
- folder;
- triggerable;
- uri.

## Safety rules

1. No broad Homey discovery when a stable Flow ID is known.
2. Perform a targeted live read before every deployment.
3. Create a timestamped pre-deploy backup where practical.
4. Compare writable flow state before writing.
5. Dry-run is the default for the Pi deployer.
6. A Homey write requires explicit apply/authorization.
7. Stop on HTTP 429; do not work around rate limiting with broad retries.
8. After a write, perform a targeted read-back.
9. Deployment is successful only when the intended writable state matches the live result.
10. On read-back mismatch, use the pre-deploy state for rollback.
11. Preserve stable Flow IDs.
12. GitHub/local reviewed source remains the intended source of truth.
13. Homey web UI may be used for visual inspection, but manual copy/paste should not be the normal EMS deployment method.
14. Do not manually start physical EV/WW actuator flows as a substitute for an end-to-end planner test.

## Validated deployment mechanism — 2026-09-05

Test Advanced Flow:

`EM v2 | 70 Planner | WW Scheduling SHADOW v0.2`

Flow ID:

`1d822642-87e8-4b0f-870e-5f2e7eef9372`

The deploy/restore cycle was validated by exact read-back hashes. This established that Advanced Flow source can be maintained from the Pi with controlled targeted deployment.

## Current production control boundary — 2026-09-12

The earlier statement that Tesla control remained on a future-to-be-migrated Homey planner is no longer current.

The Pi dynamic planner is now the active planner authority when:

`EM2_Planner_Authority = PI`

The production command path is:

```text
Pi dynamic planner
      ↓
/control/current
      ↓
Homey PI Dynamic Planner Bridge v1.2.4
      ↓
EM2_Power_Intent
      ↓
EV / WW adapters
      ↓
validation gates
      ↓
Homey physical actuators
      ↓
Easee/Tesla + boiler
```

The active Pi bridge is:

`EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.2.4 AUTHORITY-GUARD [READY]`

The guarded Homey producer remains the rollback path when the selector is returned to `HOMEY`.

The selector is the sole actual planner-authority gate. Pi `control-authority.json` may carry configuration or diagnostic state, but it does not form a second live authority gate.

## Controlled cutover validation — 2026-09-12

The controlled self-test first required a ready zero-target Pi command and only then switched `EM2_Planner_Authority` from HOMEY to PI. It retained PI only after observing takeover of the canonical `EM2_POWER_INTENT_V0.2`; otherwise it would have rolled back.

### Tesla

A non-zero Pi command was passed through the normal production chain, not by manually starting the actuator.

Observed:

- 4830 W / 7 A Pi target;
- EV gate PASS;
- actuator physical write performed;
- Easee charging at 7 A / approximately 4.9 kW;
- later return to 0 A physically paused charging again.

Result: **Pi → Homey → Tesla ON/OFF PASS.**

### Warm water

A non-zero Pi WW command was passed through the normal production chain.

Observed:

- boiler `onoff = true`;
- approximately 2.03 kW / 8.97 A physical load;
- restore to normal Pi target switched boiler to `onoff = false`, 0 W.

Result: **Pi → Homey → boiler ON/OFF PASS.**

## EV health correction

The active EV gate is:

`EM v2 | 80 Validation | EV Power Adapter Gate v0.2.5 OBSERVABILITY-ONLY HEALTH`

`EM2_EV_Telemetry_Health` remains diagnostic only at this gate. A stale capability-timestamp heuristic must not independently veto an otherwise coherent EV command. The other intent/state/revision/electrical/translation checks remain active.

## Intended workflow for future changes

```text
GitHub/local source
    -> targeted live audit
    -> backup
    -> diff
    -> explicit approval
    -> apply
    -> targeted read-back
    -> semantic/physical validation
    -> PASS
```

For planner-authority changes, additionally verify the Homey selector and `/control/current` readiness. Do not introduce a second authority gate.

## Homey load policy

Use the lowest practical Homey API load:

- stable IDs;
- targeted reads;
- no unnecessary discovery;
- no serial API bursts;
- no retries after 429 unless the specific production component already has bounded, reviewed backoff behavior;
- prepare and compare data locally on the Pi;
- separate observation from mutation;
- explicit writes only.
