# Pi → Homey Advanced Flow Deployment

Status: VALIDATED
Validated: 2026-09-05

## Purpose

EMS Advanced Flow changes can be prepared and deployed from the Raspberry Pi
instead of manually copying code through the Homey web interface.

This is a deployment mechanism only. It does not change the EMS architecture
or move control responsibility from Homey to the Pi.

## Architecture

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

## Pi locations

Read-only auditor:

/home/jeroen/ems/runtime/homey-deploy/homey_flow_audit.py

Controlled deployer:

/home/jeroen/ems/runtime/homey-deploy/homey_flow_deploy.py

Backups:

/home/jeroen/ems/backups/homey-flows/

Homey CLI project:

/home/jeroen/ems-homey-adapter

Homey CLI:

/home/jeroen/ems-homey-adapter/node_modules/.bin/homey

Node runtime:

/opt/node-v24.20.0/bin

## Homey Advanced Flow interface

Targeted read:

homey api flow get-advanced-flow --id <FLOW_ID> --json

Controlled update:

homey api flow update-advanced-flow \
  --id <FLOW_ID> \
  --body @<PAYLOAD_FILE> \
  --json

Only these Advanced Flow fields are sent in an update payload:

- name
- enabled
- cards

Read-only response metadata such as the following must not be sent back:

- id
- broken
- folder
- triggerable
- uri

## Safety rules

1. No broad Homey discovery when a stable Flow ID is known.
2. Perform a targeted live read before every deployment.
3. Create a timestamped pre-deploy backup.
4. Compare writable flow state before writing.
5. Dry-run is the default.
6. A Homey write requires explicit --apply.
7. Stop on HTTP 429; do not retry or work around rate limiting.
8. After a write, perform a targeted read-back.
9. Deployment is successful only when the writable-state SHA-256 matches
   the candidate SHA-256.
10. On read-back mismatch, attempt rollback to the pre-deploy state.
11. Verify rollback with another targeted read and hash comparison.
12. Preserve stable Flow IDs.
13. GitHub/local reviewed source remains the intended source of truth.
14. Homey web UI may be used for visual inspection, but manual copy/paste
    should not be the normal EMS deployment method.

## Validated end-to-end test

Test Advanced Flow:

EM v2 | 70 Planner | WW Scheduling SHADOW v0.2

Flow ID:

1d822642-87e8-4b0f-870e-5f2e7eef9372

The following sequence was successfully validated on 2026-09-05:

1. Targeted Advanced Flow inventory/read.
2. Full live JSON capture.
3. Timestamped local backup.
4. Exact MATCH test against captured live state.
5. Deliberate candidate name change detected as DIFF.
6. Dry-run correctly blocked the write.
7. Writable-only hashing validated.
8. Explicit --apply changed only the test candidate state.
9. Targeted read-back produced the exact candidate hash.
10. Original pre-deploy state was redeployed.
11. Final read-back reproduced the original writable-state hash.

Original writable-state SHA-256:

338af6557a01ac7fa9e265cb211ca19f109dad47cf801c192067d68339bd3644

Temporary TEST-CANDIDATE SHA-256:

074011e52ef8eabcf0ed4df59a7691b721b52402034b6e5e638960f9f64c4c54

Final result:

PASS — deploy and restoration verified by exact read-back hashes.

## Intended workflow

For future EMS Homey corrections:

GitHub/local source
    -> build/review candidate
    -> targeted live audit
    -> backup
    -> diff
    -> explicit approval
    -> --apply
    -> read-back verification
    -> PASS

Do not deploy when the candidate has not been reviewed.

## Current architecture boundary

This mechanism does NOT mean that existing Homey control logic is
automatically migrated to the Pi.

In particular, Tesla control remains on the existing Homey chain until its
current restoration/validation is complete and an explicit migration decision
is made.

The Pi deployment mechanism is infrastructure for safely maintaining existing
Homey flows.

## Homey load policy

Use the lowest practical Homey API load:

- stable IDs
- targeted reads
- no unnecessary discovery
- no serial API bursts
- no retries after 429
- prepare and compare data locally on the Pi
- separate observation from mutation
- explicit writes only
