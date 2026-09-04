# EV deadline responsiveness — predeploy structural diff gate

Status: **PREP ONLY / NOT DEPLOYED**

Deployment is allowed only if all checks below PASS against a fresh read of the two live Homey flows immediately before write.

## Adapter structural diff
Target: `445cb82c-5e1f-43c3-b2cf-f2d78fec6e16`

Expected:
- same flow id and enabled state;
- same 4 card ids;
- same cron card and 1-minute cadence;
- same manual Start card;
- same note/topology;
- only action card `33333333-3333-4333-8333-333333333333.args.code` changes;
- candidate code source must equal `deadline-goal-adapter-v0.1.1.full.js`;
- candidate contains no device capability write.

Anything else => **FAIL / ABORT DEPLOYMENT**.

## Core structural diff
Target: `227f8d3b-7551-46dd-837d-1b8c69add824`

Expected:
- same flow id/name/enabled state;
- every current card retained byte-for-byte semantically;
- existing 5-minute cron unchanged;
- existing manual Start unchanged;
- Core HomeyScript action `33333333-0981-4981-8981-333333333333` source unchanged;
- exactly one new card: `55555555-0981-4981-8981-555555555555`;
- new card is Logic variable_changed for `EM2_EV_Goal_Input_Status`, variable id `a800bcdc-ca0a-481e-94ff-419b90f5348b`;
- new card outputSuccess points only to the existing Core HomeyScript action.

Anything else => **FAIL / ABORT DEPLOYMENT**.

## Order gate
1. Adapter update first.
2. Verify unchanged website command across consecutive polls does not mutate `EM2_EV_Goal_Input_Status`.
3. Only then add Core event trigger.

Reason: adding the trigger before marker idempotency is proven would wake Core every minute because the live v0.1 marker contains a fresh timestamp.

## Scope gate
No write/update to:
- Power Intent;
- EV Power Adapter;
- EV Gate;
- EV Actuator;
- Easee device;
- `FRESH_MS`;
- any unrelated Homey flow.
