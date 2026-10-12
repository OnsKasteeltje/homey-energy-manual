# Honeywell Actuator V0.1 — six-room local DRY-RUN

**Status:** SHADOW / READ_ONLY; prototype evaluation only. No production promotion, no Homey writes, no Honeywell writes, no publisher, no new timer.

Related design: draft PR #243, `docs/architecture/heating-honeywell-actuator-v0.1-design.md` on `design/heating-honeywell-actuator-v0-1-20261012`.

## Purpose and limitations

The standalone evaluator `services/pi/control/heating/evaluate_honeywell_actuator_dry_run_v0_1.py` reads five existing **Pi-local** JSON artifacts and prints one JSON result to stdout. It has no network or home-control imports, makes no device read or write, and does not change the live four-room Homey Intent/Adapter/Gate bridge.

It reports exactly six Honeywell Heating rooms:
`woonkamer`, `eetkamer`, `keuken`, `serre`, `douwe_slaapkamer`, `erker_douwe`.

Every room stays visible even when blocked. In particular, the currently observed **permanent overrides** for both Douwe rooms result in `HOLD` and `HONEYWELL_OVERRIDE_ACTIVE`. They are not permanent scope exclusions. An upstream `preheatScope=false` would be shown separately as `SIX_ROOM_SCOPE_MIGRATION_REQUIRED`. In the accepted live Pi smoke test, **none** of the six rooms had this denial: observed V0.3 and V0.5 already cover all six. This prototype deliberately does **not** modify V0.3, V0.5, the still-four-room Homey intent allowlist, Homey device map or command cardinality.

The local input snapshots are:
- `/home/jeroen/ems/data/heating-preheat-shadow-v0.3.json`
- `/home/jeroen/ems/data/heating-control-gate-shadow-v0.5.json`
- `/home/jeroen/ems/data/heating-production-grant-v0.1.json`
- `/home/jeroen/ems/runtime/tools/honeywell/output/honeywell-state.json`
- `/home/jeroen/ems/data/energy-state-v2.json`

The `p1.meta.source_sample_at` timestamp, **not** a republished energy-state time, determines fresh P1 measurement evidence. Absent or stale original P1 sample fails closed. An instantaneous exporting snapshot is not evidence of **sustained** available PV export or a reservation against EV/WW.

The evaluator checks schema, source ages, planner grant and validity, V0.5 SHADOW checks, P1 instantaneous import/export, current vendor mode, override expiry, thermostat ID, Honeywell-vs-V0.3 target/mode agreement, existing room scope, prospective target <= future Honeywell UP and first increment <=0.5 °C, and expiry at the original UP. It rejects physical reset: V0.5 `WOULD_KEEP_TEMP` does not establish physical ownership and also fails closed.

Output schema: `EMS_HEATING_HONEYWELL_ACTUATOR_DRY_RUN_V0.1`. Per room `status` is either `BLOCKED` or `CANDIDATE_ONLY` with `denialReasons`; `simulatedAction` is either `HOLD` or `WOULD_SET_TEMP`. A candidate is a *diagnostic what-if*, not a live-permit: `physicalWrites=0`, `physicalWriteAllowed=false`, `liveExecutionAllowed=false`, `physicalOwnershipProven=false`. `edgeProofMissing` lists the unresolved sustained P1 check, Homey edge read, ACK, independent Honeywell readback, physical ownership and grant-revision binding.

### Leesbare blokkaderedenen (presentation-only)

`--human` toont een compacte Nederlandstalige uitleg per kamer, met gedeelde P1-/plannerblokkades één keer bovenaan. Zonder deze optie blijft het bestaande JSON-contract beschikbaar. Elke kamer heeft daarnaast een JSON-veld `diagnosis` met `headline`, `category`, `advice`, `primaryCode`, `otherReasons` en `technicalOnly`.

**De oorspronkelijke `denialReasons` blijven byte-for-byte de autoritatieve technische codes.** Redenen worden uitsluitend voor presentatie gegroepeerd: een ontbrekende planner-grant verklaart vaak `ROOM_NOT_IN_PRODUCTION_GRANT`; een V0.5 HOLD veroorzaakt doorgaans `V05_NO_NEW_SET_CANDIDATE` en een lege target. Die vervolgdetails staan nog in JSON, maar verdringen de hoofdoorzaak niet. Een Honeywell-permanente override heeft, zolang bronkwaliteit geldig is, voor die kamer presentatievoorrang boven algemene weers-/energiecondities. Bronfouten of ongeldige gegevens krijgen voorrang boven normale wachtcondities.

Voorbeelden uit de eerste Pi-observatie: *Geen geplande temperatuurverhoging*, *Planner geeft verwarming geen ruimte*, *Geen bruikbaar P1-overschot*, *Permanente Honeywell-override op 16 °C*. Dit zijn **waargenomen redenen bij een specifiek moment**, geen blijvende toestand.

## Safe manual PI smoke test from an isolated worktree

Run these commands **on the Pi**. They only read runtime JSON and use a separate temporary worktree: `main` and deployed services remain untouched.

```bash
set -euo pipefail
cd /home/jeroen/ems/repo/homey-energy-manual
git fetch origin feat/heating-actuator-six-room-dry-run-v0-1
WT="/tmp/ems-heating-dryrun-$(date +%s)"
git worktree add --detach "$WT" FETCH_HEAD

python3 "$WT/tests/planner/heating/test_honeywell_actuator_dry_run_v0_1.py"

# Leesbaar overzicht, zonder de technische codes:
python3 "$WT/services/pi/control/heating/evaluate_honeywell_actuator_dry_run_v0_1.py" --human

# Machineleesbaar resultaat inclusief alle technische blokkades:
python3 "$WT/services/pi/control/heating/evaluate_honeywell_actuator_dry_run_v0_1.py" |
python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["roomCount"] == 6
assert d["physicalWrites"] == 0
assert d["liveExecutionAllowed"] is False
for room in d["rooms"]:
    assert room["diagnosis"]["headline"]
print("PASS: six-room dry-run only, no physical writes")
'

git worktree remove "$WT"
```

If the process is run outside the normal 5-minute Heating/P1 freshness windows, **all rooms may legitimately report `BLOCKED`**. This is a fail-closed result, not evidence of a defect. The first live-snapshot smoke test must report all six room keys, no physical writes, and the two Douwe overrides as blockers if they are still present. A missing source file or malformed schema must never be patched over with synthetic production data.

## Live Pi smoke-test result — 2026-10-12

- Isolated worktree at `4e0bf1b9b`; **18/18 tests PASS**.
- Six rooms reported, `physicalWrites=0`, `liveExecutionAllowed=false`; Python printed `PASS: six-room dry-run, no physical writes`.
- All six rooms `BLOCKED` at the time of observation: `NO_PRODUCTION_HEATING_GRANT`, `P1_NOT_EXPORTING_WITHOUT_IMPORT`, and `V05_NO_NEW_SET_CANDIDATE`; some additionally reported no upcoming `UP` or target bound failure.
- `douwe_slaapkamer` and `erker_douwe`: vendor mode `permanent_override`, with `HONEYWELL_OVERRIDE_ACTIVE`; both visible and never commanded.
- No `UPSTREAM_SIX_ROOM_SCOPE_MIGRATION_REQUIRED` or `V05_SIX_ROOM_SCOPE_MIGRATION_REQUIRED` on any room. Thus no upstream `preheatScope` extension has been demonstrated as necessary; the remaining known four-room boundary is Pi/ Homey SHADOW egress.

A **positive** `CANDIDATE_ONLY` case under actual PV export is still **not** demonstrated. This observation does not validate physical write, sustained export or independent edge-readback.

## Future integration gates (not in this PR)

1. Keep the observed six-room V0.3/V0.5 scope intact; validate room/group consistency, and extend only the still-four-room Pi/Homey SHADOW egress allowlist, room-to-device mapping, command-cardinality checks and tests to six in a **separate read-only change**.
2. Add evidence-based P1 stability and executive-edge checks, allowlist/time-limited canary, authoritative revision-binding, durable owned temporary override with acknowledgement and independent readback, then watchdog-safe release. These must be distinct reviewed changes.
3. No automatic publisher or actuator installation and no LIVE permission until separately approved. Physical Honeywell changes remain **strictly forbidden** during this increment.
