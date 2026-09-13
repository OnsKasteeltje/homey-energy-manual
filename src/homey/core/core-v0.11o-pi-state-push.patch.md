# Core v0.11o — direct Homey Core → Pi state push

Status: REVIEWED PATCH CANDIDATE — not deployed yet.

## Verified live baseline

Direct Homey inspection on 2026-09-13 verified:

- Advanced Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`
- live flow name: `EM v2 | 00 Core Tick | v0.11n PINNED SOURCE`
- live public state version: `EM2_CORE_STATE_V0.11n`
- public schema: `2.12`
- trigger topology: every 5 minutes, manual start, plus `EM2_EV_Goal_Input_Status` change
- Core already builds the canonical `payload` and writes it to `EM2_Public_State`
- live v0.11n includes `tesla.deadline_max_a`

GitHub's previously captured complete Core source is older (`core-v0.11m.live-homey.js`), so the exact v0.11n live flow must be preserved as rollback evidence before any Homey mutation.

## Objective

Add a one-way LAN transport of the already-built canonical `payload`:

`Homey Core → POST /state/energy → Pi status API → atomic /home/jeroen/ems/data/energy-state-v2.json`

The transport must not add any Homey device polling and must not make GitHub part of the runtime control path.

## Transport contract

Endpoint:

`http://192.168.1.42:3100/state/energy`

Authentication:

`Authorization: Bearer <EM2_PI_State_Ingest_Token>`

Body:

The existing `payload` object, serialized unchanged with `JSON.stringify(payload)`.

The token is a Homey Logic secret and must never be committed to GitHub. The Pi counterpart remains in `/etc/ems/state-ingest.env` as `EMS_STATE_INGEST_TOKEN`.

## Minimal Core patch

Add constants near the existing Core constants:

```js
const PI_STATE_URL='http://192.168.1.42:3100/state/energy';
const PI_STATE_TOKEN_VAR='EM2_PI_State_Ingest_Token';
```

After the existing:

```js
await set('EM2_Public_State','string',JSON.stringify(payload));
```

insert:

```js
let piStatePush={status:'SKIPPED_TOKEN_MISSING',httpStatus:null,error:null};
const piStateToken=String(vv(PI_STATE_TOKEN_VAR)||'').trim();
if(piStateToken){
  try{
    const r=await fetch(PI_STATE_URL,{
      method:'POST',
      headers:{
        'Content-Type':'application/json',
        'Authorization':`Bearer ${piStateToken}`
      },
      body:JSON.stringify(payload)
    });
    piStatePush={
      status:r.ok?'ACCEPTED':'REJECTED',
      httpStatus:r.status,
      error:r.ok?null:`HTTP_${r.status}`
    };
  }catch(e){
    piStatePush={
      status:'ERROR',
      httpStatus:null,
      error:String(e?.message||e)
    };
  }
}
```

Then include `piStatePush` in the existing final `READY_FOR_PUBLISHER` status object.

## Architectural guarantees

1. No additional `Homey.devices.getDevice()` calls are introduced.
2. No additional broad `Homey.logic.getVariables()` call is introduced. The new token is read from the Core's already-fetched `vars` map via `vv(...)`.
3. The existing canonical `payload` is reused; the push does not reconstruct state.
4. LAN transport failure does not alter Homey execution or physical actuator ownership.
5. Pi remains fail-closed because stale/missing state prevents a valid planner/control command.
6. No GitHub request is required for Homey → Pi runtime state transport.
7. Pi write validation remains responsible for auth, schema, freshness, replay protection and atomic replacement.
8. The secret must never appear in source, logs or GitHub.

## Validation sequence

1. Preserve exact live v0.11n flow/source as rollback evidence.
2. Create Homey Logic variable `EM2_PI_State_Ingest_Token` with the same secret as Pi `/etc/ems/state-ingest.env`.
3. Apply the minimal patch to the exact live v0.11n script and bump publisher version to `EM2_CORE_STATE_V0.11o`.
4. Run Core once manually.
5. Verify Pi `energy-state-v2.json` receives a genuinely fresh Homey sample with publisher v0.11o.
6. Verify revision/heartbeat/source-sample semantics.
7. Run the canonical forecast chain once while its timer is still disabled.
8. Verify `/control/current` becomes READY from genuine state.
9. Re-enable only `ems-forecast-chain.timer` after validation.
10. Keep the separate Homey-dependent Pi poller timers disabled until individually reviewed.
