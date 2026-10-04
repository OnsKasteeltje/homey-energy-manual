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
AI_RESUME_TEST="tests/integrations/test_ai_request_resume_contract.py"
AI_NAV_RESUME_TEST="tests/frontend/test_ai_navigation_resume_contract.py"
FLEX_CONTEXT_TEST="tests/integrations/test_flex_context_archive_contract.py"
QUOOKER_EVIDENCE_TEST="tests/integrations/test_quooker_evidence_contract.py"
FLEX_CONTEXT_ARCHIVE="services/pi/history/archive_flex_context_snapshot.py"
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
[[ -f "$AI_RESUME_TEST" ]] || fail "$AI_RESUME_TEST missing"
[[ -f "$AI_NAV_RESUME_TEST" ]] || fail "$AI_NAV_RESUME_TEST missing"
[[ -f "$FLEX_CONTEXT_TEST" ]] || fail "$FLEX_CONTEXT_TEST missing"
[[ -f "$QUOOKER_EVIDENCE_TEST" ]] || fail "$QUOOKER_EVIDENCE_TEST missing"
[[ -f "$FLEX_CONTEXT_ARCHIVE" ]] || fail "$FLEX_CONTEXT_ARCHIVE missing"
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
