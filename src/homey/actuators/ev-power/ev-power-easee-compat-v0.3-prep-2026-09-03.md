# EM v2 | EV / Easee compatibility hardening v0.3 — PREP ONLY

Date: 2026-09-03
Status: **PREPARED / NOT DEPLOYED**
Homey mutations performed by this preparation: **none**
Physical device writes performed by this preparation: **none**

## Why this change is being prepared

Current captured runtime contracts treat 6 A as the minimum executable EV current. The live actuator accepts `requested_A === 0 || requested_A >= 6`, while the adapter and validation gate use `MIN_A=6` / `min_A===6`.

For the current Easee/Homey dynamic-current semantics, 6 A is a boundary value and is not a robust charging command. The integer command contract should therefore avoid 1–6 A entirely and use:

- `0 A` = explicit non-charging / stop-normalize intent
- `7..16 A` = executable charging range
- `1..6 A` = invalid and must never be emitted or accepted

This is a compatibility hardening only. It does **not** yet add a separate Start/Resume command. The first objective is to prove whether dynamic-current control alone is sufficient once the ambiguous 6 A command is removed.

## Proposed contract revision

New mapping identifier:

`FLOOR_3P230_MIN7_FAIL_CLOSED`

Electrical constants:

```js
const PHASES=3;
const VOLTAGE_V=230;
const MIN_A=7;
const W_PER_A=PHASES*VOLTAGE_V; // 690 W/A
const MIN_CHARGE_W=W_PER_A*MIN_A; // 4830 W
```

Mapping semantics:

```js
if (targetW === 0) requestedA = 0;
else if (targetW < 4830) requestedA = 0;
else requestedA = Math.min(MAX_A, Math.floor(targetW / 690 + Number.EPSILON));
if (requestedA > 0 && requestedA < 7) requestedA = 0;
```

The adapter remains floor-quantized: it may never request more executable EV power than supplied by upstream Power Intent, except when explicitly clamped by the configured maximum in the already-established contract.

## Adapter patch — prepared delta

Target runtime baseline:
`src/homey/adapters/ev-power/ev-power-v0.1-shadow.runtime.md`

Required semantic changes for the next deployable adapter revision:

```diff
- const PHASES=3,VOLTAGE_V=230,MIN_A=6,FRESH_MS=120000;
+ const PHASES=3,VOLTAGE_V=230,MIN_A=7,FRESH_MS=120000;

- mappingRevision:'FLOOR_3P230_FAIL_CLOSED'
+ mappingRevision:'FLOOR_3P230_MIN7_FAIL_CLOSED'
```

The resulting minimum executable 3-phase power becomes `3 × 230 × 7 = 4830 W`.

## Validation gate patch — prepared delta

Target runtime baseline:
`src/homey/actuators/ev-power/ev-power-adapter-gate-v0.2.1.runtime.md`

```diff
- minA===6
- maxA>=6
+ minA===7
+ maxA>=7

- mapping:'FLOOR_3P230_FAIL_CLOSED'
+ mapping:'FLOOR_3P230_MIN7_FAIL_CLOSED'

- adapter?.safety?.mappingRevision==='FLOOR_3P230_FAIL_CLOSED'
+ adapter?.safety?.mappingRevision==='FLOOR_3P230_MIN7_FAIL_CLOSED'
```

The gate must fail any adapter output in the forbidden `1..6 A` range.

Recommended explicit guard:

```js
const commandRangeOK = a===0 || (Number.isInteger(a) && a>=7 && a<=maxA);
```

and include `commandRangeOK` in `checks.translation` or as a separate `checks.commandRange` gate.

## Live actuator patch — prepared delta

Target runtime baseline:
`src/homey/actuators/ev-power/ev-power-v0.2-live-ownership.runtime.md`

```diff
- requestedA>=0&&requestedA<=16&&((requestedA===0)||(requestedA>=6))
+ requestedA>=0&&requestedA<=16&&((requestedA===0)||(requestedA>=7))

- mappingRevision==='FLOOR_3P230_FAIL_CLOSED'
+ mappingRevision==='FLOOR_3P230_MIN7_FAIL_CLOSED'
```

Additionally, before any future Start/Resume support is introduced, the live actuator should keep the existing targeted-read architecture and add only read-back that is proven necessary. Do not introduce a second unconditional Easee command path.

## Offline acceptance vectors

Assume fixed 3×230 V and `MAX_A=16`.

| Power Intent target_W | Expected requested_A | Executable W | Expected result |
|---:|---:|---:|---|
| 0 | 0 | 0 | ZERO_INTENT |
| 4139 | 0 | 0 | BELOW_MINIMUM_EXECUTABLE_POWER |
| 4140 | 0 | 0 | BELOW_MINIMUM_EXECUTABLE_POWER; 6 A forbidden |
| 4829 | 0 | 0 | BELOW_MINIMUM_EXECUTABLE_POWER |
| 4830 | 7 | 4830 | EXECUTABLE |
| 5519 | 7 | 4830 | QUANTIZED_DOWN |
| 5520 | 8 | 5520 | EXECUTABLE |
| 10350 | 15 | 10350 | EXECUTABLE |
| 11040 | 16 | 11040 | EXECUTABLE |
| 12000 | 16 | 11040 | CLAMPED_TO_MAX_CURRENT |

Mandatory negative tests:

- Adapter output `requested_A=1..6` => gate FAIL.
- Live actuator receiving `requested_A=1..6` => fail closed to 0 A; never propagate the forbidden value.
- Mapping revision mismatch between adapter/gate/actuator => fail closed.
- Stale intent/state/gate behavior remains unchanged.
- No new device read/write is introduced in adapter or gate.

## Deployment sequence (not executed)

1. Produce deployable adapter revision with MIN_A=7 and new mapping revision.
2. Produce matching gate revision and validate offline vectors.
3. Produce matching actuator revision.
4. Deploy adapter + gate first while physical ownership remains safe/shadow as applicable.
5. Confirm same-revision PASS at the gate.
6. Only then deploy/promote the live actuator revision.
7. Run a controlled 0 A → 7 A → 0 A smoke test and inspect charger state/read-back.
8. Add Start/Resume only if that test proves dynamic current alone cannot resume charging.

## Explicit non-goals

- No Homey flow modification in this preparation.
- No charger current write.
- No Tesla command.
- No unconditional Easee Start/Resume command.
- No polling increase.
- No change to upstream Power Intent policy.

## Decision

**Prepared recommendation:** remove 6 A from the executable EV command domain before diagnosing any remaining resume/start behavior. This isolates Easee command semantics from planner/Core policy and preserves the existing fail-closed ownership model.
