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

### Begrijpelijke voorwaarden op twee niveaus (uitsluitend presentatie)

De terminalweergave `--human` toont **ALGEMENE VOORWAARDEN** eenmaal (centrale planner, P1, brondatakwaliteit), vervolgens **PER KAMER** uitsluitend de *aanvullende* kamervoorwaarden (Honeywell override, volgende schemastap, temperatuur/veiligheid, kamerkoppeling). Een kamer heeft **geen vaste of unieke blokkadereden**: meerdere voorwaarden kunnen tegelijkertijd gelden, of geen aanvullende kamerbeperkingen naast algemene blokkades.

De algemene melding `NO_PRODUCTION_HEATING_GRANT` wordt **'Voorverwarmen momenteel niet ingepland'**. De uitleg gebruikt rechtstreeks `heating.reason` uit `heating-production-grant-v0.1.json`, waar zinvol aangevuld met het daadwerkelijk gerapporteerde `priorityOwner`. Bekende actuele contractredenen krijgen een specifieke verklaring, waaronder `NO_HEATING_PREHEAT_CANDIDATE`, `DYNAMIC_PLAN_STALE_OR_NOT_CURRENT`, `NO_CURRENT_DYNAMIC_PLAN_SLOT`, `FLEX_PRIORITY_PRE_DATES_HEATING` en `FLEX_PRIORITY_DID_NOT_GRANT_HEATING`. Een **onbekende code wordt niet geraden**: de weergave meldt dat een precieze plannerreden nog niet is vertaald, en bewaart de originele `plannerReasonCode` en `priorityReasonCode` in JSON.

De bronkwaliteitscontrole vermeldt voortaan de **betreffende bron** in plaats van het algemene *'Onvoldoende betrouwbare brongegevens'*. Bijvoorbeeld `P1_SOURCE_STALE_OR_UNTIMED` wordt *'P1-meter: niet actueel of ontbrekend meettijdstip'*; analoog voor Honeywell, Heating V0.3, V0.5 en de centrale Heating grant. Een ongedocumenteerde technische bronfout wordt zichtbaar met de ruwe code, niet als een gegokte oorzaak. De oorspronkelijke foutcodes veranderen niet.

Het JSON-resultaat behoudt **ongewijzigd** `globalDenialReasons` en per kamer `denialReasons` (de leidende technische blokkadecodes). Nieuw zijn `generalConditions` met categorie/titel/uitleg en per kamer `roomConditions` plus `technicalOnly`. Afgeleide foutmeldingen zoals `V05_NO_NEW_SET_CANDIDATE` en `V05_ROOM_CHECKS_NOT_ALL_TRUE` blijven zichtbaar als technische details, maar worden niet als onafhankelijke hoofdoorzaak herhaald. Er zijn geen wijzigingen aan de Heating-beslisregels, permissies, device writes of Homey-bridge.

Deze uitleg is een **momentopname**, geen bewijs van stabiel PV-overschot of toestemming voor LIVE-aansturing.

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
assert isinstance(d["generalConditions"], list)
for room in d["rooms"]:
    assert isinstance(room["roomConditions"], list)
    assert isinstance(room["denialReasons"], list)
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
