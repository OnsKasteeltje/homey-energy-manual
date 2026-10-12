# Heating Honeywell Actuator V0.1 — design and release conditions

**Status:** DRAFT / DESIGN ONLY, 2026-10-12. Not authorization for LIVE operation.  
**Change class:** documentation only; no physical writes, no Homey Flow activation, no systemd timer activation.  
**Target architectural scope:** all six Heating zones: `woonkamer`, `eetkamer`, `keuken`, `serre`, `douwe_slaapkamer`, `erker_douwe`. Scope is **capability**, not permission: a zone is actionable only if its current Honeywell state, schedule, planner and execution guards allow it. The current permanent overrides in both Douwe zones categorically block EMS preheat writes for those zones until the homeowner restores a schedule-following state. The existing four-room Homey SHADOW bridge is not yet a six-room implementation.

## 1. Verified starting point

- PR #239 (observed Honeywell target semantic history) and PR #240 (isolated contract test) are merged. On 2026-10-12 the Pi deployment and a read-only live acceptance query both passed: six `heating.honeywell_target.*` state rows, six `targetSeries` API projections, seven-day target-history window.
- The read-only Homey device listing matches the four pinned preheat IDs in `docs/commissioning/heating-homey-shadow-chain-v0.1.md` **and also exposes thermostat devices for `douwe_slaapkamer` and `erker_douwe`**. Homey advertises per-zone **temporary temperature override by clock time**, **temporary override by number of hours**, and **reset temperature to normal schedule** Flow actions for all six. Their existence is **not yet proof that an EMS-initiated write/expiry/readback succeeds**. The two Douwe zones currently report 16 °C permanent overrides in canonical Honeywell target-history evidence.
- The existing PI chain is Heating V0.3 -> Flex -> production Dynamic Pi Planner Heating Grant V0.1 -> progression V0.4 -> control gate V0.5. The grant is planner allocation authority, not realtime execution permission; the current V0.5 remains explicitly `READ_ONLY/SHADOW` and `physicalWriteAllowed=false`.
- The former Pi -> Homey SHADOW Intent/Adapter/Gate bridge is proven for **four** rooms but deliberately parked. The Pi intent publisher currently enforces a four-room allowlist, the Homey adapter has four mapped thermostat IDs, and the adapter/gate contracts require exactly four commands. Extending the **future versioned** interface to six rooms needs coordinated source, config, validation and regression updates; do not silently expand or activate the existing SHADOW objects. Their `SHADOW_ONLY`, `physicalWrite=false`, and `liveExecutionAllowed=false` assertions **must not** simply be toggled into live actuation. Shadow ownership is never proof of physical ownership.

## 2. Target architecture, no second planner

```text
Existing Pi Dynamic Planner + Heating grant
    -> V0.3 / V0.4 / V0.5 (unchanged SHADOW observability)
    -> NEW dedicated, short-lived actuation permit/intent boundary
    -> Homey: existing mapped Intent/Adapter/Gate concepts, revalidated
    -> Homey: SINGLE Honeywell actuator (only LIVE writer)
    -> Honeywell zone temporary override (bounded expiry)
    -> independent vendor-side Honeywell observation + ownership journal
    -> readback/expiry watchdog; optionally owned per-zone reset
```

A new LIVE permit is a **separate, explicitly versioned contract**, not an implicit interpretation of the current V0.5 `WOULD_*` output. It must bind the current canonical planner grant revision, V0.5 decision, exact room/device mapping, opportunity ID, requested target, original scheduled UP time, expiry, short TTL, and unique idempotency key. No standalone PV allocation and no parallel heating planner.

### Six-room target scope versus staged activation

The six-room Honeywell monitoring/dashboard/history is now independently confirmed by the live Pi dry-run. The same dry-run found no `UPSTREAM_SIX_ROOM_SCOPE_MIGRATION_REQUIRED` or `V05_SIX_ROOM_SCOPE_MIGRATION_REQUIRED` for any room: in the observed snapshot V0.3 and V0.5 already flag all six rooms as `preheatScope=true`. This does **not** expand the existing four-room Pi -> Homey SHADOW publisher, adapter or gate. The future actuator interface must support **all six** canonical room keys with validated, deterministic device mapping:

| Room key | Observed Homey thermostat ID | Current scope interpretation |
| --- | --- | --- |
| `woonkamer` | `6a79bb86-8c02-43db-be22-6f51e01efc6d` | Current four-room SHADOW mapping; future conditional actuator eligibility |
| `eetkamer` | `dd7ef4a3-ed9f-4e4d-92bb-090502068421` | Current four-room SHADOW mapping; future conditional actuator eligibility |
| `keuken` | `b7aec05b-953f-41e1-a7b4-ad09c9bf911e` | Current four-room SHADOW mapping; future conditional actuator eligibility |
| `serre` | `13625cb2-8fb5-4466-a21f-7addd8d72a88` | Current four-room SHADOW mapping; future conditional actuator eligibility |
| `douwe_slaapkamer` | `f74252a1-2879-4967-ba2d-41f56364e39b` | Add to future interface; **currently HOLD due to permanent override** |
| `erker_douwe` | `f9db36cd-8c0f-4beb-aa28-0127597652cf` | Add to future interface; **currently HOLD due to permanent override** |

The state-based eligibility policy applies uniformly to all six rooms; the canary allowlist is a separate, narrow *rollout* decision. A room that is not in the canary or whose mode is not `follow_schedule` remains `HOLD`. Neither permanent overrides nor human temporary overrides may be cleared just to make a room eligible.

Migration prerequisite: **preserve the already-observed six-room V0.3/V0.5 `preheatScope`**, check that every upstream room/group and opportunity is handled consistently, and separately update the **four-room Pi publisher allowlist**, Homey device mapping, command-cardinality checks and tests **as a separate SHADOW-only change**. Do not alter Honeywell user overrides, enable the publisher timer, or interpret existing upstream scope as a commissioned six-room write path.

### Runtime acceptance evidence — 2026-10-12

User-operated isolated-worktree smoke test of PR #244 on the Pi passed 18/18 `unittest` regressions and printed `PASS: six-room dry-run, no physical writes`. All six rooms were `BLOCKED`: the production Heating grant was `HOLD`, P1 was not exporting without import, and V0.5 proposed no new SET. Both Douwe rooms were observed in `permanent_override` and explicitly rejected as `HONEYWELL_OVERRIDE_ACTIVE`. None of the six rooms had a scope-migration denial in this sample. This **validates fail-closed observation**, not a positive candidate under real PV conditions and not physical actuation.

## 3. Required guards before every SET or progression increment

All must pass at the *execution edge*; otherwise `HOLD` with structured reason, and no write:

1. **Explicit enablement:** global physical-actuation kill switch defaults OFF; separate per-room canary allowlist; only the sole Homey Honeywell actuator may write. Pi Honeywell integration and its OAuth credentials remain read-only.
2. **Valid chain:** correct schema/revision, source order, and freshness for V0.3, Flex, production grant, V0.4, V0.5, and actuation permit. Planner grant must explicitly cover this room/current opportunity; revoked/expired/out-of-order grants cannot execute. Check current EV priority (including hard deadline) and non-EV allocation; do not create a separate Heating PV pot.
3. **Realtime P1:** independently read a *fresh, timestamped* Homey P1 source at execution; verify actual export and no import using the canonical sign convention. Use a conservative sustained surplus/hysteresis derived from measured Heating impact and commissioning observations; do **not** invent a fixed watt threshold. The forward forecast and the grant's advisory P1 field are insufficient. Unknown quality, sign, age, or source => deny.
4. **Honeywell comfort authority:** fresh Honeywell vendor state and schedule consistent with the current mapped device, expected zone/system mode, currently `follow_schedule` for a first start, and no temporary/permanent **user** override. All six zones use exactly the same conditional override guard. A permanent override (currently both Douwe rooms) means `HOLD`, never an exclusion from architectural scope and never an invitation to reset the user's override. Subsequent increments require verified *EMS-owned* temporary override state. If current target, overrideUntil, systemMode, or scheduled switchpoint changed since the permit, invalidate and replan. Fail closed on missing room temperature.
5. **Only scheduled UP:** requested target strictly above the current effective Honeywell baseline and not above the next scheduled UP target, never advance a DOWN transition or invent demand. The existing 0.5°C step rule, measured-step-reached progression, room group guard, and Quatt CV safeguard remain enforced. No intentional grid import.
6. **Expiry:** write only a *temporary* zone override ending no later than the original next scheduled UP; never set generic `target_temperature` (which may produce a persistent override). Validate the Homey Flow card's time argument semantics, time zone, DST, rounding, and whether a same-day/overnight deadline can be represented accurately. When not provable, do not execute.
7. **One in-flight operation:** per-room mutex; semantic idempotency across restarts and retries; persist `PREPARED` before sending. Never repeat an ambiguous send blindly. Limit command rate and require acknowledgement/readback before any further increment.
8. **Time budgets:** short-lived permit, bounded command/readback timeout and bounded override duration. Concrete freshness seconds, hysteresis and maximum override lifetime are tuning parameters to substantiate using real device/P1 telemetry before LIVE, not assumed design facts.

## 4. Physical ownership, acknowledgement and rollback

The single actuator owns only an *individually acknowledged and independently observed* EMS-created override, never a whole thermostat or the user's schedule.

- Persist a per-room operation journal: command ID/idempotency key, intent/revisions, room/device ID, opportunity ID, original effective baseline and schedule UP, target, intended expiry, sent time, Homey action acknowledgement, fresh Honeywell readback (setpointMode, targetTemperature_C, overrideUntil and source timestamp), and explicit ownership state.
- A Homey Flow action acknowledgement alone is transport success, **not** physical proof. Homey's immediate cached `target_temperature` is insufficient as sole proof: reconcile with a newer independent Honeywell collector observation. Until confirmed, block additional writes.
- Use explicit states `NOT_OWNED -> PREPARED -> SENT -> ACKED -> VERIFIED_OWNED -> RELEASED/EXPIRED`, with `AMBIGUOUS` and `RECOVERY_REQUIRED` branches. On restart reconcile persisted journal with current Honeywell state before any new action.
- `KEEP` means no new write. `RESET_TO_SCHEDULE` is allowed only after **actual** physical ownership was verified, live target/mode still correspond to the EMS operation, no intervening manual action exists, and a per-zone (never all-zones) reset is available and verified.
- If the homeowner changes a target or mode, treat it as **human authority**: revoke EMS ownership, stop issuing Heating writes, and do not overwrite or blindly reset it. If ownership/readback is ambiguous, stop writing and alert; rely on the original vendor-side bounded temporary expiry rather than performing an unowned reset.
- On grant loss, disappearing PV, import, schedule/override change, watchdog timeout, or crash, block starts/increments. For an already *verified-owned* temporary override, attempt bounded reset after safe ownership revalidation; on connection loss the vendor temporary expiry is the last-resort fail-safe. Never claim successful rollback without readback. Do not reset all zones.

## 5. Public contract and diagnostics

For each of the **six rooms**, expose **read-only**: `lastProposedCommand`, permit/grant revision, gate results, P1 sample time and validity, observed Honeywell target/mode, exact expiry, command status, actuator ownership state, write acknowledgement, independent readback status/time, last rollback result and safety denial reason. A zone with an active permanent or user temporary override explicitly reports `HOLD`/`HONEYWELL_OVERRIDE_ACTIVE`, not an unavailable or omitted room. Preserve the existing seven-day semantic target history as independent **presentation/retrospective** evidence only; do not feed the history graph back as control authority.

Existing Homey device and Flow-card discovery was read-only. Do not use `Homey.devices.setCapabilityValue('target_temperature', ...)` for LIVE preheat and do not infer that the old SHADOW Gate's read proves a successful physical write.

## 6. Acceptance gates before any LIVE canary

- **Source contracts:** dry-run permit validator covers all six rooms, rejects stale/future/out-of-order source, wrong room/ID, inconsistent grant revision, missing P1 timestamp/quality, any import, no sustained surplus, manual/permanent/temporary override, unknown system mode, missing Honeywell data, DOWN transition, target overflow, non-0.5°C progression, and expired/ambiguous local time. Specifically verify both Douwe rooms remain visible but `HOLD` while permanent overrides apply, and may only become *candidates* after a separately observed user-initiated return to `follow_schedule`.
- **Six-room mapping and Homey surface tests:** assert that all six mapped device IDs and exact per-zone temporary override/reset Flow cards exist and have understood argument semantics; prove that current four-room Pi/Homey SHADOW command and pinned-Logic cardinality expectations have been explicitly migrated and regression-tested before any six-room actuator candidate. Do not invoke a write as part of discovery.
- **Replay & crash tests:** idempotency, retries, rate limiting, acknowledgement without readback, Homey/API outage, Pi/Homey restart, grant loss, sudden grid import, manual takeover, schedule mutation, delayed vendor update, DST crossing and premature expiry. No unowned reset permitted under any test.
- **Observability:** run an extended no-write dry-run against real PV/P1/Heating data and verify each proposed start/rejection, expected expiry, and mode. Record no energy/cost or comfort advantage as established until it is actually measured.
- **One-room canary only, explicit approval:** choose **one currently eligible `follow_schedule` room** from the six-room interface, establish an auditable per-room physical enable with automatic expiry, verify vendor-side temporary override and automatic return to schedule. An overridden Douwe room is *not* eligible just because its device is mapped. Expand to multiple rooms only after recorded, successful readback/rollback and grid-import/comfort evaluation. A passed SHADOW Gate is not a LIVE release.

## 7. Non-goals and release decision

No Honeywell writes from the Pi, no Homey publisher auto-enable during this design, no Homey/GitHub state publishing, no new scheduler, no switch of CV/Quatt logic, no all-zones reset, no changes to original Honeywell comfort schedule, and no use of historical `targetSeries` as control input.

**Status now: DESIGN ONLY / LIVE BLOCKED.** The live Honeywell action-card mapping was inspected, but the physical temporary-override semantics, independent ownership readback and emergency rollback have not been commissioned. No proposed code may replace current fail-closed SHADOW assertions until a separately reviewed versioned LIVE boundary is ready.
