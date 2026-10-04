#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOC="docs/architecture/CURRENT-EMS-STATE.md"
STRUCTURE_DOC="docs/architecture/repository-structure.md"
HONEYWELL_DOC="docs/architecture/honeywell-integration.md"
CONNECTLIFE_DOC="docs/architecture/connectlife-integration.md"
HOMEY_DOC="services/pi/integrations/homey/README.md"
POLICY="src/pi/ems-runtime/planner/contract-policy.json"
STATE_INGEST="services/pi/integrations/homey/ingress/state_ingest.py"
HISTORY_ARCHIVE="services/pi/api/status/history_archive.py"
EV_CONTROL_INGEST="services/pi/integrations/homey/ingress/ev_control_ingest.py"
EV_CONTROL_PUSH="apps/homey/observability/ev/ev-control-pi-push-v0.1.homeyscript.js"
AI_EV_EVIDENCE_TEST="tests/integrations/test_ai_ev_evidence_contract.py"
AI_CONTEXT_EVIDENCE_TEST="tests/integrations/test_ai_v0_3_context_contract.py"
AI_V04_CONTEXT_TEST="tests/integrations/test_ai_v0_4_flex_context_contract.py"
AI_EVIDENCE_QUALITY_TEST="tests/integrations/test_ai_evidence_quality_contract.py"
AI_SEMANTIC_EVENT_TEST="tests/integrations/test_ai_semantic_event_evidence_contract.py"
AI_CURRENT_DEADLINE_TEST="tests/integrations/test_ai_current_deadline_command_contract.py"
SEMANTIC_EVENT_HISTORY_TEST="tests/integrations/test_semantic_event_history_contract.py"
AI_RESUME_TEST="tests/integrations/test_ai_request_resume_contract.py"
AI_NAV_RESUME_TEST="tests/frontend/test_ai_navigation_resume_contract.py"
FLEX_CONTEXT_TEST="tests/integrations/test_flex_context_archive_contract.py"
HEATING_OBSERVABILITY_TEST="tests/integrations/test_heating_observability_contract.py"
QUOOKER_EVIDENCE_TEST="tests/integrations/test_quooker_evidence_contract.py"
FLEX_CONTEXT_ARCHIVE="services/pi/history/archive_flex_context_snapshot.py"
SEMANTIC_EVENT_ARCHIVE="services/pi/history/archive_semantic_events.py"
SEMANTIC_EVENT_SERVICE="deploy/systemd/ems-semantic-event-history.service"
SEMANTIC_EVENT_TIMER="deploy/systemd/ems-semantic-event-history.timer"
QUOOKER_EVIDENCE_INGEST="services/pi/integrations/homey/ingress/quooker_evidence_ingest.py"
QUOOKER_EVIDENCE_PUSH="apps/homey/observability/quooker/quooker-pi-push-v0.1.homeyscript.js"
HEALTH_EVIDENCE="services/pi/health/ems_health.py"
PLANNER_HISTORY="services/pi/history/archive_planner_snapshot.py"
PERFORMANCE="services/pi/history/ems_performance.py"
HONEYWELL="services/pi/integrations/honeywell"
CONNECTLIFE="services/pi/integrations/connectlife"
AI_ANALYSIS="services/pi/api/analysis/server.py"
AI_ANALYSIS_DOC="docs/architecture/ems-ai-analysis-agent.md"
AI_ANALYSIS_UNIT="deploy/systemd/ems-ai-analysis.service"
FRONTEND_CADDY="deploy/caddy/ems-frontend-v2.Caddyfile"
FORECAST_CHAIN="deploy/systemd/ems-forecast-chain.service"
PV_FORECAST_V2_SOURCE="services/pi/forecast/pv/build_pv_forecast_v2.py"
PV_FORECAST_V2_UNIT="deploy/systemd/ems-pv-forecast-v2-shadow.service"
HEATING_V03_RUNNER="services/pi/planner/heating/run_heating_preheat_shadow_v0_3.py"
FLEX_PRIORITY_SHADOW="services/pi/planner/joint/build_flex_priority_shadow_v0_1.py"
PI_DEPLOY="scripts/deploy_ems_pi.sh"
HEATING_V05_BUILD="services/pi/control/heating/build_heating_control_gate_shadow_v0_5.py"
HEATING_V05_RUNNER="services/pi/control/heating/run_heating_control_gate_shadow_v0_5.py"
HEATING_V05_SERVICE="deploy/systemd/ems-heating-control-gate-shadow.service"
HEATING_V05_TIMER="deploy/systemd/ems-heating-control-gate-shadow.timer"
HEATING_V05_INSTALL="deploy/install/install_heating_control_gate_shadow_v0_5.sh"
HEATING_V05_OBSERVABILITY_INSTALL="deploy/install/install_heating_v05_observability.sh"
HEATING_HOMEY_PUBLISHER="services/pi/integrations/homey/egress/publish_heating_control_intent_shadow.py"
HEATING_HOMEY_ADAPTER="src/homey/adapters/heating-control/heating-control-v0.1.shadow.js"
HEATING_HOMEY_GATE="src/homey/validation/heating-control-adapter-gate-v0.1.shadow.js"
HEATING_HOMEY_COMMISSION="services/pi/commissioning/install_heating_homey_shadow_chain_v0_1.py"
HEATING_HOMEY_SERVICE="deploy/systemd/ems-heating-homey-shadow-publish.service"
HEATING_HOMEY_TIMER="deploy/systemd/ems-heating-homey-shadow-publish.timer"
HEATING_HOMEY_TEST="tests/integrations/test_heating_homey_shadow_contract.py"
HEATING_HOMEY_NODE_TEST="tests/homey/heating-control-shadow.test.mjs"
HEATING_HOMEY_RESUME_TEST="tests/integrations/test_heating_homey_resume_contract.py"
HEATING_HOMEY_CLI_TEST="tests/integrations/test_heating_homey_cli_noninteractive_contract.py"
HEATING_HOMEY_RATE_LIMIT_TEST="tests/integrations/test_heating_homey_publish_rate_limit_contract.py"
HEATING_HOMEY_COMMISSION_DOC="docs/commissioning/heating-homey-shadow-chain-v0.1.md"
HEATING_CADENCE_TEST="tests/integrations/test_heating_shadow_cadence_contract.py"
HEATING_CADENCE_INSTALL="deploy/install/install_heating_shadow_cadence_v0_1.sh"
HEATING_V03_TIMER="deploy/systemd/ems-heating-preheat-shadow.timer"
HEATING_FLEX_TIMER="deploy/systemd/ems-flex-priority-shadow.timer"
HEATING_V04_TIMER="deploy/systemd/ems-heating-preheat-progression-shadow.timer"
HEATING_V05_TIMER="deploy/systemd/ems-heating-control-gate-shadow.timer"
HEATING_HOMEY_PUBLISH_TIMER="deploy/systemd/ems-heating-homey-shadow-publish.timer"
BASE_REF="${1:-}"

fail() { echo "ARCHITECTURE GATE: FAIL: $*" >&2; exit 1; }
pass() { echo "ARCHITECTURE GATE: PASS: $*"; }

cd "$REPO"
[[ -f "$DOC" ]] || fail "$DOC missing"
[[ -f "$STRUCTURE_DOC" ]] || fail "$STRUCTURE_DOC missing"
[[ -f "$HONEYWELL_DOC" ]] || fail "$HONEYWELL_DOC missing"
[[ -f "$CONNECTLIFE_DOC" ]] || fail "$CONNECTLIFE_DOC missing"
[[ -f "$HOMEY_DOC" ]] || fail "$HOMEY_DOC missing"
[[ -f "$POLICY" ]] || fail "$POLICY missing"
[[ -f "$STATE_INGEST" ]] || fail "$STATE_INGEST missing"
[[ -f "$HISTORY_ARCHIVE" ]] || fail "$HISTORY_ARCHIVE missing"
[[ -f "$EV_CONTROL_INGEST" ]] || fail "$EV_CONTROL_INGEST missing"
[[ -f "$EV_CONTROL_PUSH" ]] || fail "$EV_CONTROL_PUSH missing"
[[ -f "$AI_EV_EVIDENCE_TEST" ]] || fail "$AI_EV_EVIDENCE_TEST missing"
[[ -f "$AI_CONTEXT_EVIDENCE_TEST" ]] || fail "$AI_CONTEXT_EVIDENCE_TEST missing"
[[ -f "$AI_V04_CONTEXT_TEST" ]] || fail "$AI_V04_CONTEXT_TEST missing"
[[ -f "$AI_EVIDENCE_QUALITY_TEST" ]] || fail "$AI_EVIDENCE_QUALITY_TEST missing"
[[ -f "$AI_SEMANTIC_EVENT_TEST" ]] || fail "$AI_SEMANTIC_EVENT_TEST missing"
[[ -f "$AI_CURRENT_DEADLINE_TEST" ]] || fail "$AI_CURRENT_DEADLINE_TEST missing"
[[ -f "$SEMANTIC_EVENT_HISTORY_TEST" ]] || fail "$SEMANTIC_EVENT_HISTORY_TEST missing"
[[ -f "$AI_RESUME_TEST" ]] || fail "$AI_RESUME_TEST missing"
[[ -f "$AI_NAV_RESUME_TEST" ]] || fail "$AI_NAV_RESUME_TEST missing"
[[ -f "$FLEX_CONTEXT_TEST" ]] || fail "$FLEX_CONTEXT_TEST missing"
[[ -f "$QUOOKER_EVIDENCE_TEST" ]] || fail "$QUOOKER_EVIDENCE_TEST missing"
[[ -f "$FLEX_CONTEXT_ARCHIVE" ]] || fail "$FLEX_CONTEXT_ARCHIVE missing"
[[ -f "$SEMANTIC_EVENT_ARCHIVE" ]] || fail "$SEMANTIC_EVENT_ARCHIVE missing"
[[ -f "$SEMANTIC_EVENT_SERVICE" ]] || fail "$SEMANTIC_EVENT_SERVICE missing"
[[ -f "$SEMANTIC_EVENT_TIMER" ]] || fail "$SEMANTIC_EVENT_TIMER missing"
[[ -f "$QUOOKER_EVIDENCE_INGEST" ]] || fail "$QUOOKER_EVIDENCE_INGEST missing"
[[ -f "$QUOOKER_EVIDENCE_PUSH" ]] || fail "$QUOOKER_EVIDENCE_PUSH missing"
[[ -f "$HEALTH_EVIDENCE" ]] || fail "$HEALTH_EVIDENCE missing"
[[ -f "$PLANNER_HISTORY" ]] || fail "$PLANNER_HISTORY missing"
[[ -f "$PERFORMANCE" ]] || fail "$PERFORMANCE missing"
[[ -d "$HONEYWELL" ]] || fail "$HONEYWELL missing"
[[ -d "$CONNECTLIFE" ]] || fail "$CONNECTLIFE missing"
[[ -f "$FORECAST_CHAIN" ]] || fail "$FORECAST_CHAIN missing"
[[ -f "$PV_FORECAST_V2_SOURCE" ]] || fail "$PV_FORECAST_V2_SOURCE missing"
[[ -f "$PV_FORECAST_V2_UNIT" ]] || fail "$PV_FORECAST_V2_UNIT missing"

python3 - "$POLICY" <<'PY'
import json, sys
p=json.load(open(sys.argv[1])); e=[]
if p.get('productionContractMode')!='FIXED': e.append('productionContractMode must be FIXED')
if p.get('productionContractId')!='ENGIE_3Y_2026_2029': e.append('productionContractId must be ENGIE_3Y_2026_2029')
d=p.get('dynamicPricing') or {}; s=p.get('safety') or {}
if d.get('enabledForProduction') is not False: e.append('dynamic pricing must be disabled for production')
if d.get('automaticFallbackAllowed') is not False: e.append('dynamic fallback must be disabled')
if s.get('failClosed') is not True: e.append('failClosed must be true')
if s.get('automaticContractModeSwitchAllowed') is not False: e.append('automatic contract-mode switching must be disabled')
if e: raise SystemExit('; '.join(e))
PY
pass "contract-policy invariants valid"

grep -q 'Canonical current-state document' "$DOC" || fail "canonical document marker missing"
grep -q 'productionContractMode = FIXED' "$DOC" || fail "FIXED contract architecture rule missing from canonical document"
grep -q 'dynamic pricing is \*\*disabled for production\*\*' "$DOC" || fail "dynamic-production prohibition missing from canonical document"
grep -q 'fail closed' "$DOC" || fail "fail-closed architecture rule missing from canonical document"
pass "canonical architecture invariants documented"

grep -q 'from history_archive import archive_state_history' "$STATE_INGEST" || fail "state ingest does not archive accepted Homey pushes"
grep -q 'archive_state_history(payload)' "$STATE_INGEST" || fail "state history archive hook missing"
grep -q 'ems-history.sqlite' "$HISTORY_ARCHIVE" || fail "history archive target is not canonical SQLite"
pass "Homey push-fed local history archive present"

grep -q 'ev_requested_a' "$HISTORY_ARCHIVE" || fail "Homey state archive must retain EV requested-current evidence"
grep -q 'manager_reason' "$HISTORY_ARCHIVE" || fail "Homey state archive must retain EMS manager reason evidence"
grep -q 'EMS_HOMEY_EV_CONTROL_EVIDENCE_V0.1' "$EV_CONTROL_INGEST" || fail "EV control evidence ingest schema missing"
grep -q 'ev_control_events' "$EV_CONTROL_INGEST" || fail "EV control event archive table missing"
grep -q '/state/ev-control' services/pi/api/status/server.py || fail "EV control evidence endpoint missing"
grep -q '/state/ev-control' "$EV_CONTROL_PUSH" || fail "Homey EV evidence push does not target local Pi endpoint"
grep -q "controlImpact:'NONE'" "$EV_CONTROL_PUSH" || fail "Homey EV evidence push must remain control-neutral"
if grep -q 'Homey.devices' "$EV_CONTROL_PUSH"; then fail "EV control evidence push must not read devices"; fi
node - "$EV_CONTROL_PUSH" <<'JS' || fail "EV control evidence HomeyScript syntax invalid"
const fs = require("fs");
const path = process.argv[2];
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
new AsyncFunction(fs.readFileSync(path, "utf8"));
JS
python3 "$AI_EV_EVIDENCE_TEST" || fail "AI V0.2 EV evidence contract failed"
pass "EV decision/reason evidence is local, historical and control-neutral"

grep -q 'EMS_HOMEY_QUOOKER_EVIDENCE_V0.1' "$QUOOKER_EVIDENCE_INGEST" || fail "Quooker evidence ingest schema missing"
grep -q 'quooker_control_events' "$QUOOKER_EVIDENCE_INGEST" || fail "Quooker evidence archive table missing"
grep -q '/state/quooker' services/pi/api/status/server.py || fail "Quooker evidence endpoint missing"
grep -q '/state/quooker' "$QUOOKER_EVIDENCE_PUSH" || fail "Homey Quooker evidence push does not target local Pi endpoint"
grep -q "controlImpact:'NONE'" "$QUOOKER_EVIDENCE_PUSH" || fail "Homey Quooker evidence push must remain control-neutral"
if grep -q 'Homey.devices' "$QUOOKER_EVIDENCE_PUSH"; then fail "Quooker evidence push must not read devices"; fi
node - "$QUOOKER_EVIDENCE_PUSH" <<'JS' || fail "Quooker evidence HomeyScript syntax invalid"
const fs = require("fs");
const path = process.argv[2];
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
new AsyncFunction(fs.readFileSync(path, "utf8"));
JS
python3 "$QUOOKER_EVIDENCE_TEST" || fail "Quooker evidence archive contract failed"
pass "Quooker evidence path is local, historical and control-neutral"

grep -q 'EMS_PI_HEALTH_V0.1' "$HEALTH_EVIDENCE" || fail "standard EMS health evidence schema missing"
grep -q '"readOnly": True' "$HEALTH_EVIDENCE" || fail "EMS health evidence must declare read-only"
grep -q '"controlWrites": False' "$HEALTH_EVIDENCE" || fail "EMS health evidence must declare no control writes"
grep -q 'recentIncidentSignals' "$HEALTH_EVIDENCE" || fail "EMS health evidence must expose recent incident signals"
grep -q 'lastExecution' "$HEALTH_EVIDENCE" || fail "EMS health evidence must verify timer-triggered service execution"
grep -q 'services/pi/health' scripts/deploy_ems_pi.sh || fail "target-structure Pi health source is not deployed"
grep -q 'TARGET-STRUCTURE HEALTH FILES' scripts/ems_pi_drift_check.sh || fail "target-structure Pi health source is not drift-checked"
grep -q '/usr/local/bin/ems-health' scripts/deploy_ems_pi.sh || fail "ems-health command is not installed by deployment"
pass "standardized read-only EMS health evidence present"

grep -q 'planner-history.sqlite' "$PLANNER_HISTORY" || fail "planner decision history target missing"
grep -q 'PLAN_EMBEDDED_DECISION_OUTPUT' "$PLANNER_HISTORY" || fail "planner history does not declare planner-owned frozen context"
if grep -Eq '^[[:space:]]*(STATE_FILE|WW_FILE)[[:space:]]*=|load\([[:space:]]*(STATE_FILE|WW_FILE)[[:space:]]*\)' "$PLANNER_HISTORY"; then fail "planner decision history must not re-read mutable live state after planning"; fi
grep -q '/home/jeroen/ems/runtime/history/archive_planner_snapshot.py' "$FORECAST_CHAIN" || fail "forecast chain does not archive hardened planner decisions"
grep -q 'services/pi/history' scripts/deploy_ems_pi.sh || fail "target-structure Pi history source is not deployed"
grep -q 'TARGET-STRUCTURE HISTORY FILES' scripts/ems_pi_drift_check.sh || fail "target-structure Pi history source is not drift-checked"
pass "planner decision history uses atomic planner-owned context"

grep -q 'EMS_PI_FLEX_CONTEXT_SNAPSHOT_V0.1' "$FLEX_CONTEXT_ARCHIVE" || fail "flex context history schema missing"
grep -q 'planner-history.sqlite' "$FLEX_CONTEXT_ARCHIVE" || fail "flex context history must use planner-history SQLite"
if grep -Eq 'Homey\.|urllib|requests|urlopen|http://' "$FLEX_CONTEXT_ARCHIVE"; then fail "flex context archive must remain Pi-local with no Homey/network calls"; fi
grep -q 'ems-flex-context-history.timer' "$HEALTH_EVIDENCE" || fail "EMS health must monitor flex context history timer"
[[ -f deploy/systemd/ems-flex-context-history.service ]] || fail "flex context history service missing"
[[ -f deploy/systemd/ems-flex-context-history.timer ]] || fail "flex context history timer missing"
grep -q '/home/jeroen/ems/runtime/history/archive_flex_context_snapshot.py' deploy/systemd/ems-flex-context-history.service || fail "flex context service does not use canonical runtime history source"
python3 "$FLEX_CONTEXT_TEST" || fail "flex context history contract failed"
pass "Heating and WW flex context is archived read-only for retrospective analysis"

grep -q 'EMS_PI_SEMANTIC_EVENT_ARCHIVE_V0.1' "$SEMANTIC_EVENT_ARCHIVE" || fail "semantic event archive schema missing"
grep -q 'ems-history.sqlite' "$SEMANTIC_EVENT_ARCHIVE" || fail "semantic events must use canonical EMS history SQLite"
grep -q 'historicalBackfill.*False' "$SEMANTIC_EVENT_ARCHIVE" || fail "semantic event archive must forbid historical backfill"
if grep -Eq 'Homey\.|urllib|requests|urlopen|http://|https://' "$SEMANTIC_EVENT_ARCHIVE"; then
  fail "semantic event archive must remain Pi-local with no Homey/network calls"
fi
grep -q 'ems-semantic-event-history.timer' "$HEALTH_EVIDENCE" || fail "EMS health must monitor semantic event history timer"
grep -q '/home/jeroen/ems/runtime/history/archive_semantic_events.py' "$SEMANTIC_EVENT_SERVICE" || fail "semantic event service does not use canonical runtime history source"
grep -Fqx 'OnCalendar=*-*-* *:*:50' "$SEMANTIC_EVENT_TIMER" || fail "semantic event history cadence must be fixed at :50"
grep -Fqx 'AccuracySec=5s' "$SEMANTIC_EVENT_TIMER" || fail "semantic event history timer accuracy must remain bounded"
python3 "$SEMANTIC_EVENT_HISTORY_TEST" || fail "semantic event history contract failed"
pass "semantic EMS state changes are archived locally without creating control authority"

grep -q 'heating-control-gate-shadow-v0.5.json' "$FLEX_CONTEXT_ARCHIVE" || fail "flex context archive must include Heating V0.5 control-gate evidence"
grep -q '"controlGate"' "$FLEX_CONTEXT_ARCHIVE" || fail "flex context snapshot must project Heating V0.5 control-gate evidence"
grep -q 'ems-heating-control-gate-shadow.service' deploy/systemd/ems-flex-context-history.service || fail "flex context archive must run after Heating V0.5 control-gate"
grep -q 'heatingControlGateV05' "$HEALTH_EVIDENCE" || fail "EMS health must expose Heating V0.5 artifact freshness"
grep -q 'ems-heating-preheat-shadow.timer' "$HEALTH_EVIDENCE" || fail "EMS health must monitor Heating V0.3 timer"
grep -q 'ems-flex-priority-shadow.timer' "$HEALTH_EVIDENCE" || fail "EMS health must monitor Flex Priority timer"
grep -q 'ems-heating-preheat-progression-shadow.timer' "$HEALTH_EVIDENCE" || fail "EMS health must monitor Heating V0.4 timer"
grep -q 'ems-heating-control-gate-shadow.timer' "$HEALTH_EVIDENCE" || fail "EMS health must monitor Heating V0.5 timer"
[[ -f "$HEATING_OBSERVABILITY_TEST" ]] || fail "Heating observability contract test missing"
python3 "$HEATING_OBSERVABILITY_TEST" || fail "Heating V0.5 observability contract failed"
pass "Heating V0.3 -> Flex -> V0.4 -> V0.5 observability is durable and health-monitored"
[[ -f "$HEATING_V05_OBSERVABILITY_INSTALL" ]] || fail "Heating V0.5 observability installer missing"
if grep -Eq 'Homey\.|requests|urllib|urlopen|http://' "$HEATING_V05_OBSERVABILITY_INSTALL"; then
  fail "Heating V0.5 observability installer must not contain Homey/network control"
fi
pass "Heating V0.5 observability deploy remains local and control-neutral"

grep -q 'services/pi/forecast' scripts/deploy_ems_pi.sh || fail "target-structure Pi forecast source is not deployed"
grep -q -- "--exclude='forecast/'" scripts/deploy_ems_pi.sh || fail "generic runtime deploy must protect target-managed forecast directory"
grep -q 'TARGET-STRUCTURE FORECAST FILES' scripts/ems_pi_drift_check.sh || fail "target-structure Pi forecast source is not drift-checked"
grep -q '/home/jeroen/ems/runtime/forecast/pv/build_pv_forecast_v2.py' "$PV_FORECAST_V2_UNIT" || fail "PV Forecast V2 service does not use canonical runtime forecast path"
pass "PV Forecast V2 target-structure deploy/drift mapping present"

grep -q 'EMS_PI_DAY_PERFORMANCE_V0.1' "$PERFORMANCE" || fail "standard EMS performance report schema missing"
grep -q 'ems-history.sqlite' "$PERFORMANCE" || fail "EMS performance command does not use canonical measurement history"
grep -q 'planner-history.sqlite' "$PERFORMANCE" || fail "EMS performance command does not use planner replay history"
grep -q 'mode=ro' "$PERFORMANCE" || fail "EMS performance SQLite connections must be explicitly read-only"
grep -q 'PRAGMA query_only=ON' "$PERFORMANCE" || fail "EMS performance SQLite connections must enforce query_only"
grep -q 'ReadWritePaths=/home/jeroen/ems/data' "$AI_ANALYSIS_UNIT" || fail "AI analysis service must allow bounded SQLite WAL coordination in data directory"
grep -q 'constrainedOptimumAvailable' "$PERFORMANCE" || fail "EMS performance report must distinguish constrained optimum from upper bound"
grep -q 'coveragePctElapsed' "$PERFORMANCE" || fail "EMS performance must distinguish elapsed-time coverage from full-day progress"
grep -q 'dayProgressPct' "$PERFORMANCE" || fail "EMS performance must expose current-day progress separately"
grep -q '/usr/local/bin/ems-performance' scripts/deploy_ems_pi.sh || fail "ems-performance command is not installed by deployment"
grep -q 'EMS PERFORMANCE COMMAND' scripts/ems_pi_drift_check.sh || fail "ems-performance installation is not drift-checked"
pass "standardized read-only EMS performance command present"

grep -q 'services/pi/integrations/honeywell' scripts/deploy_ems_pi.sh || fail "Honeywell target-structure source is not deployed"
grep -q -- "--exclude='.venv/'" scripts/deploy_ems_pi.sh || fail "Honeywell local virtualenv is not protected during deployment"
grep -q 'TARGET-STRUCTURE HONEYWELL FILES' scripts/ems_pi_drift_check.sh || fail "Honeywell target-structure source is not drift-checked"
grep -q -- "-not -path './.venv/\*'" scripts/ems_pi_drift_check.sh || fail "Honeywell local virtualenv is not excluded from drift validation"
grep -q 'services/pi/integrations/honeywell/' "$HONEYWELL_DOC" || fail "Honeywell target repository boundary missing from architecture document"
grep -q '/home/jeroen/ems/runtime/tools/honeywell/' "$HONEYWELL_DOC" || fail "Honeywell runtime compatibility path missing from architecture document"
pass "Honeywell target-structure deployment preserves host-local runtime state"

grep -Fq -- "-not -path './thermal/*'" "$PI_DEPLOY" || fail "generic Pi deploy unmanaged-file check must ignore derived runtime/thermal state"
grep -Fq -- "--exclude='thermal/'" "$PI_DEPLOY" || fail "generic Pi rsync must preserve derived runtime/thermal state"
grep -q 'load_optional_json(QUATT_FILE' "$HEATING_V03_RUNNER" || fail "Heating V0.3 runner must fail closed on unavailable Quatt artifact"
grep -q 'MAX_HEATING_AGE_SECONDS = 420' "$FLEX_PRIORITY_SHADOW" || fail "Flex Priority must bound Heating V0.3 freshness"
grep -q '"sourceFreshness"' "$FLEX_PRIORITY_SHADOW" || fail "Flex Priority must expose Heating source freshness"
grep -q 'elif not heating_current:' "$FLEX_PRIORITY_SHADOW" || fail "Flex Priority must refuse stale Heating grants"
pass "Heating preheat runtime-state preservation and freshness propagation present"

[[ -f "$HEATING_CADENCE_TEST" ]] || fail "Heating deterministic cadence test missing"
[[ -f "$HEATING_CADENCE_INSTALL" ]] || fail "Heating deterministic cadence installer missing"
[[ -f "$HEATING_V03_TIMER" ]] || fail "Heating V0.3 timer missing"
[[ -f "$HEATING_FLEX_TIMER" ]] || fail "Heating Flex timer missing"
[[ -f "$HEATING_V04_TIMER" ]] || fail "Heating V0.4 timer missing"
[[ -f "$HEATING_V05_TIMER" ]] || fail "Heating V0.5 timer missing"
[[ -f "$HEATING_HOMEY_PUBLISH_TIMER" ]] || fail "Heating Homey publish timer missing"
python3 "$HEATING_CADENCE_TEST" || fail "Heating deterministic cadence contract failed"
grep -Fqx 'OnCalendar=*-*-* *:04/5:00' "$HEATING_V03_TIMER" || fail "Heating V0.3 cadence must start refresh minute at :00"
grep -Fqx 'AccuracySec=1s' "$HEATING_V03_TIMER" || fail "Heating V0.3 timer accuracy must be 1s"
grep -Fqx 'OnCalendar=*-*-* *:*:10' "$HEATING_FLEX_TIMER" || fail "Heating Flex cadence must be fixed at :10"
grep -Fqx 'AccuracySec=1s' "$HEATING_FLEX_TIMER" || fail "Heating Flex timer accuracy must be 1s"
if grep -Fq 'OnUnitActiveSec=' "$HEATING_FLEX_TIMER"; then
  fail "Heating Flex timer must not use relative OnUnitActiveSec cadence"
fi
if grep -Fq 'OnBootSec=' "$HEATING_FLEX_TIMER"; then
  fail "Heating Flex timer must not use separate boot phase"
fi
grep -Fqx 'OnCalendar=*-*-* *:*:20' "$HEATING_V04_TIMER" || fail "Heating V0.4 cadence must be fixed at :20"
grep -Fqx 'AccuracySec=1s' "$HEATING_V04_TIMER" || fail "Heating V0.4 timer accuracy must be 1s"
grep -Fqx 'OnCalendar=*-*-* *:*:30' "$HEATING_V05_TIMER" || fail "Heating V0.5 cadence must be fixed at :30"
grep -Fqx 'AccuracySec=1s' "$HEATING_V05_TIMER" || fail "Heating V0.5 timer accuracy must be 1s"
grep -Fqx 'OnCalendar=*-*-* *:*:35' "$HEATING_HOMEY_PUBLISH_TIMER" || fail "Heating Homey publish cadence must be fixed at :35"
grep -Fqx 'AccuracySec=1s' "$HEATING_HOMEY_PUBLISH_TIMER" || fail "Heating Homey publish timer accuracy must be 1s"
if grep -Eq 'Homey\.|requests|urllib|urlopen|http://' "$HEATING_CADENCE_INSTALL"; then
  fail "Heating cadence installer must not contain Homey/network control"
fi
pass "Heating local SHADOW cadence is phase-locked through V0.5; Homey publish slot remains parked"

[[ -f "$HEATING_V05_BUILD" ]] || fail "Heating V0.5 builder missing"
[[ -f "$HEATING_V05_RUNNER" ]] || fail "Heating V0.5 runner missing"
[[ -f "$HEATING_V05_SERVICE" ]] || fail "Heating V0.5 service missing"
[[ -f "$HEATING_V05_TIMER" ]] || fail "Heating V0.5 timer missing"
[[ -f "$HEATING_V05_INSTALL" ]] || fail "Heating V0.5 installer missing"
grep -q 'EMS_HEATING_CONTROL_GATE_SHADOW_V0.5' "$HEATING_V05_BUILD" || fail "Heating V0.5 schema missing"
grep -q '"controlWrites": False' "$HEATING_V05_BUILD" || fail "Heating V0.5 must disallow control writes"
grep -q '"physicalWriteAllowed": False' "$HEATING_V05_BUILD" || fail "Heating V0.5 must disallow physical writes"
grep -q '"physicalWrite": False' "$HEATING_V05_BUILD" || fail "Heating V0.5 commands must be hypothetical"
grep -q 'RESET_TO_HONEYWELL_SCHEDULE_IF_SHADOW_OWNED' "$HEATING_V05_BUILD" || fail "Heating V0.5 rollback contract missing"
grep -q 'HOMEY_HONEYWELL_ACTUATOR_ONLY' "$HEATING_V05_BUILD" || fail "Heating V0.5 single-writer boundary missing"
if grep -Eq '^[[:space:]]*(import|from)[[:space:]]+(requests|urllib|httpx|aiohttp)|Homey\.' "$HEATING_V05_BUILD" "$HEATING_V05_RUNNER"; then
  fail "Heating V0.5 SHADOW must not contain a Homey/network client"
fi
python3 -m py_compile "$HEATING_V05_BUILD" "$HEATING_V05_RUNNER" || fail "Heating V0.5 Python syntax invalid"
pass "Heating V0.5 remains Pi-local, shadow-only and physical-write-free"

[[ -f "$HEATING_HOMEY_PUBLISHER" ]] || fail "Heating Homey SHADOW publisher missing"
[[ -f "$HEATING_HOMEY_ADAPTER" ]] || fail "Heating Homey SHADOW adapter missing"
[[ -f "$HEATING_HOMEY_GATE" ]] || fail "Heating Homey SHADOW gate missing"
[[ -f "$HEATING_HOMEY_COMMISSION" ]] || fail "Heating Homey SHADOW commissioning installer missing"
[[ -f "$HEATING_HOMEY_SERVICE" ]] || fail "Heating Homey SHADOW publisher service missing"
[[ -f "$HEATING_HOMEY_TIMER" ]] || fail "Heating Homey SHADOW publisher timer missing"
[[ -f "$HEATING_HOMEY_TEST" ]] || fail "Heating Homey SHADOW Pi contract test missing"
[[ -f "$HEATING_HOMEY_NODE_TEST" ]] || fail "Heating Homey SHADOW edge contract test missing"
grep -q 'EMS_HEATING_CONTROL_INTENT_V0.1' "$HEATING_HOMEY_PUBLISHER" || fail "Heating Homey intent schema missing"
grep -q '"plannerAuthority": "SHADOW_ONLY"' "$HEATING_HOMEY_PUBLISHER" || fail "Heating Homey intent must remain shadow authority"
grep -q '"productionPlannerHeatingGrantPresent": False' "$HEATING_HOMEY_PUBLISHER" || fail "Heating Homey intent must not claim production Heating grant"
grep -q '"physicalWriteAllowed": False' "$HEATING_HOMEY_PUBLISHER" || fail "Heating Homey intent must forbid physical writes"
grep -q '"liveExecutionAllowed": False' "$HEATING_HOMEY_PUBLISHER" || fail "Heating Homey intent must explicitly forbid LIVE execution"
grep -q 'const IDS=__EMS_HEATING_IDS__;' "$HEATING_HOMEY_ADAPTER" || fail "Heating Homey adapter render token missing"
grep -q 'const IDS=__EMS_HEATING_IDS__;' "$HEATING_HOMEY_GATE" || fail "Heating Homey gate render token missing"
if grep -Eq 'setCapabilityValue|setCapabilityValues|set_devices_capabilities' "$HEATING_HOMEY_ADAPTER" "$HEATING_HOMEY_GATE"; then
  fail "Heating Homey SHADOW edge source must not contain device write APIs"
fi
grep -q 'Homey.devices.getDevice' "$HEATING_HOMEY_GATE" || fail "Heating Homey gate targeted readback missing"
grep -q 'OnCalendar=.*:35' "$HEATING_HOMEY_TIMER" || fail "Heating Homey publisher must run after V0.5 at :35"
python3 "$HEATING_HOMEY_TEST" || fail "Heating Homey Pi intent contract failed"
[[ -f "$HEATING_HOMEY_RESUME_TEST" ]] || fail "Heating Homey resume validation test missing"
python3 "$HEATING_HOMEY_RESUME_TEST" || fail "Heating Homey resume validation contract failed"
[[ -f "$HEATING_HOMEY_CLI_TEST" ]] || fail "Heating Homey noninteractive CLI test missing"
python3 "$HEATING_HOMEY_CLI_TEST" || fail "Heating Homey noninteractive CLI contract failed"
[[ -f "$HEATING_HOMEY_RATE_LIMIT_TEST" ]] || fail "Heating Homey rate-limit suppression test missing"
python3 "$HEATING_HOMEY_RATE_LIMIT_TEST" || fail "Heating Homey rate-limit suppression contract failed"
node "$HEATING_HOMEY_NODE_TEST" || fail "Heating Homey adapter/gate contract failed"
python3 -m py_compile "$HEATING_HOMEY_PUBLISHER" "$HEATING_HOMEY_COMMISSION" || fail "Heating Homey Python syntax invalid"
if grep -q 'get-variables' "$HEATING_HOMEY_COMMISSION"; then
  fail "Heating first commissioning must not bulk-discover Logic variables"
fi
if grep -q 'get-advanced-flows' "$HEATING_HOMEY_COMMISSION"; then
  fail "Heating first commissioning must not bulk-discover Advanced Flows"
fi
grep -q 'pendingOperation' "$HEATING_HOMEY_COMMISSION" || fail "Heating first commissioning write-ahead marker missing"
grep -q 'AMBIGUOUS_PARTIAL_COMMISSIONING' "$HEATING_HOMEY_COMMISSION" || fail "Heating first commissioning ambiguous-create stop missing"
grep -q '/api/manager/logic/variable/{var_id}' "$HEATING_HOMEY_COMMISSION" || fail "Heating Logic readback must be targeted by pinned ID"
grep -q -- '--resume' "$HEATING_HOMEY_COMMISSION" || fail "Heating Homey commissioning must have explicit resume validation"
grep -q 'READBACK_SPACING_SECONDS = 6' "$HEATING_HOMEY_COMMISSION" || fail "Heating Homey resume readback pacing missing"
grep -q 'WRITE_SPACING_SECONDS = 6' "$HEATING_HOMEY_COMMISSION" || fail "Heating Homey write/readback pacing missing"
grep -q 'config\["publisherTimerEnabled"\] = False' "$HEATING_HOMEY_COMMISSION" || fail "Heating READY resync must invalidate timer activation proof"
grep -q 'config.pop("lastValidatedRevision", None)' "$HEATING_HOMEY_COMMISSION" || fail "Heating READY resync must clear prior revision proof"
grep -q 'RESUME_REQUIRES_READY_STATE' "$HEATING_HOMEY_COMMISSION" || fail "Heating Homey resume must require READY state"
grep -q 'RESUME_REVISION_MISMATCH' "$HEATING_HOMEY_COMMISSION" || fail "Heating Homey resume revision gate missing"
if grep -q 'enable", "--now"' "$HEATING_HOMEY_COMMISSION"; then
  fail "Heating Homey SHADOW commissioning must not auto-enable publisher timer"
fi
grep -q 'disable", "--now"' "$HEATING_HOMEY_COMMISSION" || fail "Heating Homey SHADOW timer-off boundary missing"
grep -q 'HOMEY_SKIP_STARTUP_NOTIFIERS' "$HEATING_HOMEY_PUBLISHER" || fail "Heating publisher must suppress Homey CLI startup notifiers"
grep -q 'NO_UPDATE_NOTIFIER' "$HEATING_HOMEY_PUBLISHER" || fail "Heating publisher must suppress update-notifier writes"
grep -q 'HOMEY_SKIP_STARTUP_NOTIFIERS' "$HEATING_HOMEY_COMMISSION" || fail "Heating commissioning must suppress Homey CLI startup notifiers"
grep -q 'NO_UPDATE_NOTIFIER' "$HEATING_HOMEY_COMMISSION" || fail "Heating commissioning must suppress update-notifier writes"
grep -Fqx 'Environment=HOMEY_SKIP_STARTUP_NOTIFIERS=1' "$HEATING_HOMEY_SERVICE" || fail "Heating publisher service startup-notifier suppression missing"
grep -Fqx 'Environment=NO_UPDATE_NOTIFIER=1' "$HEATING_HOMEY_SERVICE" || fail "Heating publisher service update-notifier suppression missing"
grep -Fqx 'ProtectHome=read-only' "$HEATING_HOMEY_SERVICE" || fail "Heating publisher home sandbox must remain read-only"
if grep -Fq 'ReadWritePaths=/home/jeroen/.config' "$HEATING_HOMEY_SERVICE"; then
  fail "Heating publisher must not gain write access to user config for CLI notifier state"
fi
grep -q 'RATE_LIMIT_COOLDOWN_SECONDS = (300, 900, 1800, 3600)' "$HEATING_HOMEY_PUBLISHER" || fail "Heating Homey bounded 429 cooldown policy missing"
grep -q 'SUPPRESS_UNCHANGED' "$HEATING_HOMEY_PUBLISHER" || fail "Heating Homey semantic write suppression missing"
grep -q 'COOLDOWN_RATE_LIMIT' "$HEATING_HOMEY_PUBLISHER" || fail "Heating Homey 429 cooldown state missing"
grep -q 'heating-homey-shadow-publish-cache.json' "$HEATING_HOMEY_PUBLISHER" || fail "Heating Homey host-local publish cache missing"
grep -q -- '--runtime-only' "$HEATING_HOMEY_COMMISSION" || fail "Heating Homey runtime-only deployment mode missing"
grep -q 'RUNTIME_ONLY_REQUIRES_READY_STATE' "$HEATING_HOMEY_COMMISSION" || fail "Heating Homey runtime-only mode must require READY state"
[[ -f "$HEATING_HOMEY_COMMISSION_DOC" ]] || fail "Heating Homey commissioning documentation missing"
grep -q 'NEXT_HEATING_STEP_PRODUCTION_DYNAMIC_PI_PLANNER_GRANT' "$HEATING_HOMEY_COMMISSION_DOC" || fail "Heating continuation checkpoint missing production grant handoff"
grep -q 'Do \*\*not\*\* restart Heating work by rebuilding the Pi -> Homey SHADOW transport' "$HEATING_HOMEY_COMMISSION_DOC" || fail "Heating continuation checkpoint must prevent SHADOW transport rebuild"
grep -q 'NEXT_HEATING_STEP_PRODUCTION_DYNAMIC_PI_PLANNER_GRANT' "$DOC" || fail "Canonical current state missing Heating continuation marker"
grep -q 'first task is the authoritative production' "$DOC" || fail "Canonical current state must point Heating restart to production planner grant"
pass "Heating V0.5 -> Homey Adapter/Gate SHADOW proof remains parked, explicit and physical-write-free"
pass "Heating continuation checkpoint pins production Dynamic Pi Planner grant as next step"

grep -q 'services/pi/integrations/connectlife/' "$CONNECTLIFE_DOC" || fail "ConnectLife target repository boundary missing from architecture document"
grep -q 'read-only telemetry' "$CONNECTLIFE_DOC" || fail "ConnectLife read-only safety boundary missing from architecture document"
grep -q 'services/pi/integrations/connectlife' "$CONNECTLIFE/ems-connectlife-oven.service" || fail "ConnectLife service does not use target repository path"
grep -q 'services/pi/integrations/connectlife' "$CONNECTLIFE/install_systemd.sh" || fail "ConnectLife installer does not use target repository path"
pass "ConnectLife target-structure and read-only boundary documented"

grep -q 'services/pi/integrations/homey/ingress/state_ingest.py' "$HOMEY_DOC" || fail "Homey ingress target repository boundary missing from integration document"
grep -q 'services/pi/integrations/homey/egress/publish_pi_control_intent.py' "$HOMEY_DOC" || fail "Homey egress target repository boundary missing from integration document"
grep -q 'quooker_evidence_ingest.py' "$HOMEY_DOC" || fail "Homey Quooker observability ingress missing from integration document"
grep -q 'apps/homey/observability/quooker/quooker-pi-push-v0.1.homeyscript.js' "$HOMEY_DOC" || fail "Homey Quooker observability push missing from integration document"
pass "Homey ingress/egress repository boundary documented"

FRONTEND_NAV="frontend/shared/navigation.js"
FRONTEND_NAV_TEST="tests/frontend/test_v2_shared_navigation_contract.py"
FRONTEND_ASSET_TEST="tests/frontend/test_v2_local_assets_contract.py"
[[ -f "$FRONTEND_NAV" ]] || fail "shared Frontend V2 navigation source missing"
[[ -f "$FRONTEND_NAV_TEST" ]] || fail "shared Frontend V2 navigation contract test missing"
[[ -f "$FRONTEND_ASSET_TEST" ]] || fail "Frontend V2 local asset contract test missing"
python3 "$FRONTEND_NAV_TEST" || fail "Frontend V2 shared navigation contract failed"
pass "Frontend V2 uses one shared main-navigation source"
python3 "$FRONTEND_ASSET_TEST" || fail "Frontend V2 local asset contract failed"
pass "Frontend V2 local CSS/JS references resolve"
python3 "$AI_NAV_RESUME_TEST" || fail "AI navigation resume frontend contract failed"
pass "AI frontend preserves conversation and pending request across V2 navigation"

[[ -f "$AI_ANALYSIS" ]] || fail "AI analysis API source missing"
[[ -f "$AI_ANALYSIS_DOC" ]] || fail "AI analysis architecture document missing"
[[ -f "$AI_ANALYSIS_UNIT" ]] || fail "AI analysis systemd unit missing"
grep -q 'controlWrites.*False' "$AI_ANALYSIS" || fail "AI analysis API does not declare read-only control boundary"
grep -q 'mode=ro' "$AI_ANALYSIS" || fail "AI analysis timeline SQLite connection must be explicitly read-only"
grep -q 'PRAGMA query_only=ON' "$AI_ANALYSIS" || fail "AI analysis timeline SQLite connection must enforce query_only"
if grep -q 'immutable=1' "$AI_ANALYSIS"; then fail "AI analysis must not use immutable SQLite reads on live evidence"; fi
grep -q 'ems-performance' "$AI_ANALYSIS" || fail "AI analysis API does not use standardized EMS performance evidence"
grep -q 'ems-health' "$AI_ANALYSIS" || fail "AI analysis API does not use standardized EMS health evidence"
grep -q 'evTelemetry5m' "$AI_ANALYSIS" || fail "AI analysis API does not expose historical EV telemetry"
grep -q 'evControlEvents' "$AI_ANALYSIS" || fail "AI analysis API does not expose EV control events"
grep -q 'plannerDecisionWindow' "$AI_ANALYSIS" || fail "AI analysis API does not expose bounded planner decision evidence"
grep -q 'forecastVsActual15m' "$AI_ANALYSIS" || fail "AI analysis API does not expose no-hindsight forecast comparison"
grep -q 'boilerW' "$AI_ANALYSIS" || fail "AI analysis timeline does not expose broader flexible-load context"
python3 "$AI_CONTEXT_EVIDENCE_TEST" || fail "AI V0.3 context evidence contract failed"
grep -q 'EMS_AI_ANALYSIS_V0.4' "$AI_ANALYSIS" || fail "AI V0.4 schema missing"
grep -q 'flexContextWindow' "$AI_ANALYSIS" || fail "AI analysis does not expose historical Heating/WW flex context"
grep -q 'quookerEvents' "$AI_ANALYSIS" || fail "AI analysis does not expose historical Quooker evidence"
python3 "$AI_V04_CONTEXT_TEST" || fail "AI V0.4 flex context contract failed"
grep -q 'deadlineSemantics' "$AI_ANALYSIS" || fail "AI analysis must expose explicit EV deadline relevance semantics"
python3 "$AI_EVIDENCE_QUALITY_TEST" || fail "AI evidence quality contract failed"
grep -q 'semanticEvents' "$AI_ANALYSIS" || fail "AI analysis must expose semantic event history"
grep -q 'semanticEventCoverage' "$AI_ANALYSIS" || fail "AI analysis must expose semantic event commissioning boundary"
python3 "$AI_SEMANTIC_EVENT_TEST" || fail "AI semantic event evidence contract failed"
grep -q 'currentDeadlineCommand' "$AI_ANALYSIS" || fail "AI analysis must expose current canonical EV deadline user intent"
grep -q '/home/jeroen/ems/data/tesla-deadline-command.json' "$AI_ANALYSIS" || fail "AI current EV deadline evidence must use canonical Pi runtime command"
python3 "$AI_CURRENT_DEADLINE_TEST" || fail "AI current EV deadline command contract failed"
grep -q 'analysis_jobs' "$AI_ANALYSIS" || fail "AI resumable request cache missing"
grep -q '/agent/result' "$AI_ANALYSIS" || fail "AI resumable result endpoint missing"
python3 "$AI_RESUME_TEST" || fail "AI resumable request contract failed"
if grep -q '/control/current' "$AI_ANALYSIS"; then fail "AI analysis API must not call Pi control endpoint"; fi
grep -q 'EMS_AI_HOST=127.0.0.1' "$AI_ANALYSIS_UNIT" || fail "AI analysis API must bind loopback"
grep -q 'EnvironmentFile=-/etc/ems/ai-agent.env' "$AI_ANALYSIS_UNIT" || fail "AI analysis secret boundary missing"
grep -q 'handle /agent/\*' "$FRONTEND_CADDY" || fail "private AI analysis Caddy route missing"
grep -q 'reverse_proxy 127.0.0.1:3210' "$FRONTEND_CADDY" || fail "AI analysis Caddy route must target loopback"
pass "AI analysis service remains read-only and outside realtime control"



for legacy_unit in deploy/systemd/ems-day-history.service deploy/systemd/ems-day-history.timer deploy/systemd/ems-homey-insights.service deploy/systemd/ems-homey-insights.timer deploy/systemd/ems-pi-control-publish.service deploy/systemd/ems-pi-control-publish.timer; do [[ ! -e "$legacy_unit" ]] || fail "legacy production unit must not be deployable: $legacy_unit"; done
pass "legacy Homey polling/control-push units absent from production deploy set"

HISTORY_15M="services/pi/history/build_15m_history.py"
HISTORY_DAILY="services/pi/history/build_daily_energy_history.py"

[[ -f "$HISTORY_15M" ]] || fail "canonical 15-minute history builder missing"
[[ -f "$HISTORY_DAILY" ]] || fail "canonical daily history builder missing"

for unit in   deploy/systemd/ems-history-15m.service   deploy/systemd/ems-history-15m.timer   deploy/systemd/ems-history-daily.service   deploy/systemd/ems-history-daily.timer
do
  [[ -f "$unit" ]] || fail "canonical local history unit missing: $unit"
done

grep -q '/home/jeroen/ems/runtime/history/build_15m_history.py'   deploy/systemd/ems-history-15m.service   || fail "15-minute history service does not use canonical runtime/history source"

grep -q '/home/jeroen/ems/runtime/history/build_daily_energy_history.py'   deploy/systemd/ems-history-daily.service   || fail "daily history service does not use canonical runtime/history source"

if grep -Eq 'collect_homey_insights|collect_boiler_insights|fetch_day_history|import_em2_day_history'   deploy/systemd/ems-history-15m.service   deploy/systemd/ems-history-daily.service
then
  fail "canonical derived-history services must not poll Homey or use legacy history ingress"
fi

pass "canonical local derived-history pipeline present and isolated from legacy polling"

if [[ -n "$BASE_REF" ]]; then
  git rev-parse --verify "$BASE_REF^{commit}" >/dev/null 2>&1 || fail "base ref $BASE_REF is not a commit"
  CHANGED="$(git diff --name-only "$BASE_REF"..HEAD)"
  if printf '%s\n' "$CHANGED" | grep -Eq '^(src/pi/ems-runtime/|services/pi/|deploy/systemd/|scripts/deploy_ems_pi\.sh$|scripts/ems_architecture_gate\.sh$|scripts/ems_pi_drift_check\.sh$)'; then
    if printf '%s\n' "$CHANGED" | grep -Fxq "$DOC"; then
      pass "architecture-sensitive changes include canonical document update"
    else
      ARCH_CHANGED="$(printf '%s\n' "$CHANGED" | grep -E '^(src/pi/ems-runtime/|services/pi/|deploy/systemd/|scripts/deploy_ems_pi\.sh$|scripts/ems_architecture_gate\.sh$|scripts/ems_pi_drift_check\.sh$)' || true)"
      NON_STRUCTURAL_ARCH="$(printf '%s\n' "$ARCH_CHANGED" | grep -Ev '^(services/pi/integrations/(honeywell|connectlife|homey)/|services/pi/api/status/(server|history_archive|state_ingest)\.py$|src/pi/ems-runtime/homey-deploy/(publish_pi_control_intent|homey_flow_audit|homey_flow_deploy)\.py$|scripts/deploy_ems_pi\.sh$|scripts/ems_architecture_gate\.sh$|scripts/ems_pi_drift_check\.sh$)' || true)"
      HONEYWELL_CHANGED="$(printf '%s\n' "$ARCH_CHANGED" | grep -E '^services/pi/integrations/honeywell/' || true)"
      CONNECTLIFE_CHANGED="$(printf '%s\n' "$ARCH_CHANGED" | grep -E '^services/pi/integrations/connectlife/' || true)"
      HOMEY_CHANGED="$(printf '%s\n' "$ARCH_CHANGED" | grep -E '^(services/pi/integrations/homey/|services/pi/api/status/state_ingest\.py$|src/pi/ems-runtime/homey-deploy/(publish_pi_control_intent|homey_flow_audit|homey_flow_deploy)\.py$)' || true)"
      STATUS_STRUCTURE_CHANGED="$(printf '%s\n' "$ARCH_CHANGED" | grep -E '^services/pi/api/status/(server|history_archive|state_ingest)\.py$' || true)"
      DOCS_OK=true
      [[ -z "$HONEYWELL_CHANGED" ]] || printf '%s\n' "$CHANGED" | grep -Fxq "$HONEYWELL_DOC" || DOCS_OK=false
      [[ -z "$CONNECTLIFE_CHANGED" ]] || printf '%s\n' "$CHANGED" | grep -Fxq "$CONNECTLIFE_DOC" || DOCS_OK=false
      [[ -z "$HOMEY_CHANGED" ]] || printf '%s\n' "$CHANGED" | grep -Fxq "$HOMEY_DOC" || DOCS_OK=false
      [[ -z "$STATUS_STRUCTURE_CHANGED" ]] || printf '%s\n' "$CHANGED" | grep -Fxq "$STRUCTURE_DOC" || DOCS_OK=false
      if [[ -z "$NON_STRUCTURAL_ARCH" && "$DOCS_OK" == true ]]; then
        pass "documented target-structure migration does not change operational architecture"
      else
        echo "Architecture-sensitive files changed since $BASE_REF:" >&2
        printf '%s\n' "$ARCH_CHANGED" >&2 || true
        fail "$DOC was not updated in the same release range"
      fi
    fi
  else
    pass "no architecture-sensitive changes in release range"
  fi
fi
pass "all checks completed"
