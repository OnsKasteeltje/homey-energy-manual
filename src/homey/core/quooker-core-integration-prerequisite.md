# Quooker — Core integration prerequisite

Status: **SEMANTIC COMMIT MARKER DESIGN FROZEN / HOMEY PROVISIONED / PRODUCER UPDATE BLOCKED BY 429**

Date: 2026-08-29

## Project decision

The current Quooker signal path must **not** be used directly as an event-driven source for Core v0.11b or the Core Snapshot Aggregator.

`EM_Quooker_Last_Sample` is currently coupled to the frequent P1/heartbeat path. Using that variable directly as an aggregator trigger would cause a high-frequency wake-up and refresh of the Quooker input group. That would add avoidable Logic reads and fan-out, undermining the Homey low-load/throttling objective.

Therefore Quooker integration remains explicitly blocked until the producer emits the low-load semantic commit described below.

## Low-load semantic commit contract

Canonical marker:

`EM_Quooker_Commit`

Schema:

```json
{
  "schema": "EM_QUOOKER_COMMIT_V0.1",
  "generatedAt": "2026-08-29T00:00:00.000Z",
  "semanticRevision": 1,
  "lastSample": "2026-08-29T00:00:00.000Z",
  "active": false,
  "powerW": 0,
  "status": "UNKNOWN",
  "switchOn": false,
  "baselineL3W": null,
  "lastTransition": null,
  "lastHeatingAt": null,
  "lastHeatingPowerW": null,
  "transitionHistory": []
}
```

The Quooker producer must build this object from values it already has in memory. It must not perform a second set of Logic reads merely to construct the commit.

### Commit rules

A new commit is written only when either:

1. the effective semantic Quooker payload changes; or
2. the previous commit is old enough that a freshness keepalive is required.

`generatedAt` and the raw heartbeat/sample timestamp are excluded from the semantic signature. `semanticRevision` increments only for a semantic payload change, not for a keepalive-only refresh.

The keepalive target is **120 seconds**. This is deliberately below Core's existing **150-second Quooker freshness gate**, preserving freshness semantics while preventing a commit on every P1 heartbeat.

The producer remains the business owner of Quooker interpretation. The commit is only a compact publication boundary; it must not introduce new policy or device writes.

## Aggregator integration after producer validation

Once the producer emits `EM_Quooker_Commit` correctly:

- the Core Snapshot Aggregator triggers on `EM_Quooker_Commit changed`, never on `EM_Quooker_Last_Sample`;
- the aggregator performs one targeted read of `EM_Quooker_Commit`, rather than rereading all ten Quooker Logic variables;
- it maps the commit payload into `EM2_Core_Input.sources.quooker`;
- existing aggregator lease and semantic-write suppression remain in force;
- hourly FULL reconciliation remains a temporary safety net during SHADOW validation.

This changes the Quooker event cost from roughly ten source reads per trigger to one compact source read, while also reducing trigger frequency.

## Homey implementation state

The one-shot v0.11b provisioning flow has been updated and executed once to create `EM_Quooker_Commit` if missing. The provisioning flow was disabled immediately afterwards and remains `broken=false`.

No production Core, Quooker detector, heartbeat, aggregator Quooker trigger, device or actuator behavior was changed in that provisioning step.

The next read-only Homey autocomplete lookup, intended to resolve the newly created variable's stable ID before embedding it in producer code, returned `429 Too many requests`. Per the project throttling rule, no retry was attempted. Therefore the producer update is deliberately deferred until Homey is responsive again.

## Acceptance gate

Quooker may be promoted into the event-driven v0.11b path only after all of the following pass:

- `EM_Quooker_Commit` stable Logic ID resolved;
- producer writes commit from already-computed values, with no extra broad Logic scan;
- semantic changes produce an immediate commit;
- unchanged state produces at most the 120-second freshness keepalive;
- aggregator reads one compact commit value per Quooker event;
- parity against the existing ten Quooker source values is demonstrated;
- no material CPU or 429/rate-limit regression is observed.

Until these criteria pass, Quooker remains a **hard prerequisite / blocker for production cut-over of Core v0.11b**.