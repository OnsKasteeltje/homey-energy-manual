# Core v0.11b — Consolidated Logic Input

Status: **DESIGN / NOT DEPLOYED**

Date: 2026-08-29

Baseline: `EM v2 | 00 Core Tick | v0.11a (Targeted Device Reads)`.

## Purpose

Remove the remaining broad `Homey.logic.getVariables()` collection scan from Core without replacing it with dozens of per-variable reads.

v0.11b introduces one canonical, consolidated Logic snapshot for the external inputs Core consumes. Core keeps the proven v0.11a targeted device reads and all current policy/output semantics unchanged.

## Why not targeted Logic reads

Core currently consumes roughly 30–35 Logic inputs. Replacing one `getVariables()` call with 30–35 `getVariable({id})` requests may reduce payload size but materially increase API request count and burst fan-out. Given the observed Homey throttling history, that trade-off is not acceptable without evidence.

Therefore v0.11b MUST NOT implement naive per-variable polling.

## Proposed contract

Canonical variable:

`EM2_Core_Input`

Suggested schema:

```json
{
  "schema": "EM2_CORE_INPUT_V0.1",
  "generatedAt": "2026-08-29T00:00:00.000Z",
  "revision": 1,
  "sources": {
    "quooker": {
      "active": false,
      "powerW": 0,
      "status": "UNKNOWN",
      "switchOn": false,
      "baselineL3W": null,
      "lastSample": null,
      "lastTransition": null,
      "lastHeatingAt": null,
      "lastHeatingPowerW": null,
      "transitionHistory": []
    },
    "context": {
      "updatedAt": null,
      "pvTop4h": false,
      "priceNegative": false,
      "priceCheapNext4h": false,
      "priceExpensiveNext4h": false
    },
    "teslaGoal": {
      "deadlineActive": false,
      "deadline": null,
      "latestStart": null,
      "remainingKWh": 0,
      "status": null
    },
    "hotWater": {
      "boilerMode": false,
      "postGoalOpportunity": null
    },
    "planner": {
      "contractPriceContext": null,
      "dayHistory": null,
      "contractType": "UNKNOWN",
      "priceBuffer": []
    },
    "publication": {
      "lastPublish": null,
      "lastPublishedRevision": null,
      "lastPublisherVersion": null
    },
    "legacy": {
      "wwStateV13": null
    }
  }
}
```

The exact field set is implementation-driven: include only values actually consumed by Core v0.11a.

## Producer model

`EM2_Core_Input` is updated by a dedicated low-load input aggregator.

Preferred behavior:

- event-driven updates when relevant source variables change;
- semantic-write suppression: do not rewrite when the effective payload is unchanged;
- maintain a monotonically increasing `revision` only on semantic change;
- record `generatedAt` and per-source timestamps where freshness matters;
- no device reads inside the aggregator unless strictly required;
- no physical writes;
- no retries after `429 Too many requests`.

A low-frequency reconciliation run may be retained as a safety net, but it must not recreate the old broad polling pattern at Core cadence.

## Core v0.11b read strategy

Core keeps the v0.11a targeted device reads and replaces:

```js
Homey.logic.getVariables()
```

with one targeted read of the canonical input snapshot.

Conceptually:

```js
const coreInput = await Homey.logic.getVariable({ id: CORE_INPUT_ID });
const input = JSON.parse(String(coreInput.value || '{}'));
```

Core output variables remain updated through the existing write-suppressed `set()` helper or an equivalent implementation. The read-side optimization must not alter downstream contracts.

## Inputs to migrate

The v0.11a source currently consumes Logic data in these functional groups:

- Quooker detector state and history;
- price/PV context and freshness;
- Tesla deadline goal state;
- `WW_Boilermodus`;
- WW post-goal opportunity;
- legacy WW bootstrap state;
- Planner contract-price context, day history, contract type and PBTH buffer;
- Publisher last-publish/revision/version bookkeeping.

Before implementation, generate the exact source-variable inventory from the deployed v0.11a code and map every `vv(...)` / `byName...` read to one `EM2_Core_Input` field. No source may be silently omitted.

## No-change contract

v0.11b MUST NOT change:

- 5-minute Core cadence;
- v0.11a targeted device reads;
- state/decision schemas;
- `EM2_Control_EV` semantic producer behavior;
- WW decision semantics;
- Power Intent semantics;
- EV/WW ownership or LIVE gates;
- Publisher cadence;
- Planner semantics;
- semantic-write suppression;
- physical device-write behavior.

## Fail-closed rules

If `EM2_Core_Input` is missing, malformed or stale:

- Core must not upgrade stale data to a valid state;
- safety-relevant opportunities must fail closed;
- P1/device freshness remains governed by the existing v0.11a device-timestamp logic;
- no retry loop is allowed inside the same Core run;
- emit a clear diagnostic status rather than silently substituting defaults for mandatory inputs.

## Rollout plan

1. Freeze v0.11a as the active baseline.
2. Build the exact Logic input dependency map from v0.11a.
3. Create `EM2_Core_Input` and a dedicated aggregator in SHADOW.
4. Run the aggregator alongside v0.11a without changing Core reads.
5. Compare aggregator snapshot values against the existing `getVariables()`-derived values over multiple natural cycles.
6. Require semantic parity and freshness parity.
7. Create v0.11b Core using one targeted canonical-input read.
8. Perform one controlled smoke only if Homey is not rate-limited.
9. Soak with the same Core + Publisher + EV + WW set used for the v0.11a baseline.
10. Compare system CPU, CPU Clock and rate-limit behavior against v0.11a.

## Acceptance criteria

PASS requires:

- zero `Homey.logic.getVariables()` calls in Core;
- no 30–35-call targeted Logic fan-out;
- one canonical Logic-input read per Core run;
- semantic parity for `EM2_State`, `EM2_Decision`, `EM2_Control_WW`, `EM2_Control_EV` and `EM2_Planner_Input`;
- no new downstream fan-out;
- no physical write regression;
- no increase in 429/rate-limit frequency;
- system CPU no worse than the v0.11a integrated baseline.

## Rollback

Rollback target is the deployed v0.11a Core unchanged. The aggregator can remain disabled or SHADOW-only after rollback.

Do not combine v0.11b cut-over with Planner, Publisher, Power Intent, Gate, EV actuator or WW actuator changes.

## Next implementation step

Create the exact dependency map from the deployed v0.11a code and define which existing producer owns each field of `EM2_Core_Input`. Only after that mapping is complete should the aggregator be created.