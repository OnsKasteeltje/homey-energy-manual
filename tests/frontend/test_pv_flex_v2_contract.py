#!/usr/bin/env python3
"""Static contract checks for the PV & Flex Analysis V2 frontend."""
from pathlib import Path

index=Path("frontend/pv-flex/index.html").read_text()
state=Path("frontend/pv-flex/state/pv-flex-state.js").read_text()
render=Path("frontend/pv-flex/render/pv-flex.js").read_text()
css=Path("frontend/pv-flex/styles/pv-flex.css").read_text()

for token in ("PV & Flex Evaluatie","Besloten versus gemeten energie","EV uit PV","Overig eigen gebruik","Export","Heating opportunity","Heating intent","DAGELIJKSE EMS-EVALUATIE · GEMETEN EN GESCHAT","Dagrapport"):
    assert token in index, token
for removed in ("flex-panel","ww-lane","evlane","EV laden","heating-note","WW boiler","Heating Flex"):
    assert removed not in index, f"duplicate/legacy render surface remains: {removed}"
assert 'const API_ROOT="/web/analysis/pv-flex/day"' in state
assert '{cache:"no-store"}' in state
assert 'EMS_WEB_PV_FLEX_ANALYSIS_V1' in state
assert 'validatedSelf.reduce(' not in render, "daily KPI must not sum per-quarter clamped self-use"
assert 'function lane(' not in render
assert 'evPowerW' in render
assert 'heatingFlex' in render
assert 'actualKnown' in render
assert 'heating-opportunity-lane' in render
assert 'heating-intent-lane' in render
assert 'evPvW' in render
assert 'class:cls' in render
assert '.pv-ev' in css and '.pv-self' in css and '.pv-export' in css
assert '.heating-opportunity-lane' in css
assert '.heating-intent-lane' in css
assert '.evbar' not in css and '.evlane' not in css
assert "fetch(" not in render, "renderer must use state adapter"
assert "tip.innerHTML" not in render, "large all-values hover must be retired"
assert 'closestEvaluationSeries' in render
assert 'MIN_COVERAGE=0.95' in render
assert 'provisional-quarter' not in render and '.provisional-quarter' not in css

assert 'id="daily-report-panel"' in index
assert 'id="day-title"' in index
assert 'id="pv-chart"' in index
assert 'id="tooltip"' in index
assert '<section class="intro">' not in index
assert 'CANONIEKE V1 · BESLISSING EN UITVOERING' not in index
assert 'id="archive-status"' not in index
assert 'id="decision-evidence"' not in index
assert 'Beslissing per kwartier' not in index
assert 'Beweeg over een lijn' not in index
assert 'renderEvidence' not in render
assert 'selectedRect' not in render
assert 'hit.addEventListener("click"' not in render
assert 'hit.addEventListener("mousemove"' in render
assert 'closestEvaluationSeries' in render
assert '.evidence-panel' not in css
assert '.selected-quarter' not in css
assert 'id="report-self"' in index
assert '<section class="kpis">' not in index
assert 'daily-pv-conclusion' not in index
assert 'id="kpi-' not in index
assert 'dailySelfUseEvidence' not in render
assert 'accounting.pvSelfConsumedKWh' in render
assert '$("report-self").textContent=decimal(accounting.pvSelfConsumedKWh)' in render
assert 'grid-template-columns:repeat(5,minmax(0,1fr))' in css
assert '.kpis{' not in css
for metric in ("report-pv", "report-self", "report-self-rate", "report-import", "report-export", "daily-report-notes"):
    assert f'id="{metric}"' in index, metric
assert 'id="preheat-panel"' not in index
assert "Voorverwarming" not in index
assert "preheat-room" not in render and "renderPreheat" not in render
assert "loadHeatingPreheatShadow" not in state
assert 'loadDailyPerformance(day)' in state
assert '"/web/analysis/performance/day/"' in state
assert 'd.dateLocal!==day' in state
assert 'loadDailyPerformance(selectedDay)' in render
assert "renderDailyReport(" in render
assert 'selectedDay>=todayAmsterdam()' in render
assert 'accounting.gridExportKWh' in render
assert 'report.lines.slice(2)' in render
# UI regression: the read-only cloud ring remains SHADOW, but accepted
# 900-second archived SEMS+ quarters have been live since 25 Oct.
assert 'SEMS+ draagt nog niet bij' not in render
assert 'SHADOW, nog niet in huisbalans' not in render
assert 'opgeslagen volledig gedekte SEMS+-kwartieren' in render
assert 'Voorlopig · gemeten deel' in render
assert '["pvProducedKWh","gridImportKWh","gridExportKWh","pvSelfConsumedKWh"]' in render
assert 'requestId!==refreshId' in render
assert '.daily-report-kpis' in css and '.preheat-room' not in css

print("PASS: PV & Flex Analysis V2 single-render frontend contract")


