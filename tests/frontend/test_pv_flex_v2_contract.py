#!/usr/bin/env python3
"""Static contract checks for the PV & Flex Analysis V2 frontend."""
from pathlib import Path

index=Path("frontend/pv-flex/index.html").read_text()
state=Path("frontend/pv-flex/state/pv-flex-state.js").read_text()
render=Path("frontend/pv-flex/render/pv-flex.js").read_text()
css=Path("frontend/pv-flex/styles/pv-flex.css").read_text()

for token in ("PV & Flex Evaluatie","PV BIJ BESLISSING","Besloten versus gemeten energie","EV uit PV","Overig eigen gebruik","Export","Heating opportunity","Heating intent","DAGELIJKSE EMS-EVALUATIE · GEMETEN EN GESCHAT","Dagrapport"):
    assert token in index, token
for removed in ("flex-panel","ww-lane","evlane","EV laden","heating-note","WW boiler","Heating Flex"):
    assert removed not in index, f"duplicate/legacy render surface remains: {removed}"
assert 'const API_ROOT="/web/analysis/pv-flex/day"' in state
assert '{cache:"no-store"}' in state
assert 'EMS_WEB_PV_FLEX_ANALYSIS_V1' in state
assert 'id="kpi-self-note"' in index
assert 'const matched=d.series.filter(x=>slotEvidence(x).comparable)' in render
assert 'matched.reduce((sum,x)=>sum+x.forecast.pvForecastW/4000,0)' in render
assert 'dailySelfUseEvidence(d)' in render
assert 'id="kpi-self-rate"' in index and 'id="daily-pv-conclusion"' in index
assert 'pvSelfUsePairedCoverage' in render
assert 'Geen betrouwbaar PV-zelfgebruikpercentage' in render
assert 'Dit is gemeten energiezelfgebruik, geen bewijs' in render
assert 'validatedSelf.reduce(' not in render, "daily KPI must not sum per-quarter clamped self-use"
assert 'const kwh=v=>typeof v==="number"&&Number.isFinite(v)?' in render, "missing daily kWh must not display as zero"
assert "forecast?.confidence" in render
assert 'function lane(' not in render
assert 'evPowerW' in render
assert 'heatingFlex' in render
assert 'actualKnown' in render
assert 'heating-opportunity-lane' in render
assert 'heating-intent-lane' in render
assert 'Tesla werkelijk' in render
assert 'evPvW' in render
assert 'class:cls' in render
assert '.pv-ev' in css and '.pv-self' in css and '.pv-export' in css
assert '.heating-opportunity-lane' in css
assert '.heating-intent-lane' in css
assert '.evbar' not in css and '.evlane' not in css
assert 'boilerPowerW' in render, 'EV and boiler measured power are compared with plans'
assert "fetch(" not in render, "renderer must use state adapter"
assert "tip.innerHTML" not in render, "large all-values hover must be retired"
assert 'closestEvaluationSeries' in render
assert 'hit.addEventListener("click"' in render
assert 'renderEvidence(slot,Date.now())' in render
assert 'MIN_COVERAGE=0.95' in render
assert 'provisional-quarter' not in render and '.provisional-quarter' not in css
assert 'class:"selected-quarter",visibility:"hidden"' in render
assert 'selectedRect.setAttribute("visibility","visible")' in render
assert 'renderEvidence(null,nowMs)' in render
assert 'id="kpi-pv-note"' in index and 'id="kpi-export-note"' in index

assert 'id="daily-report-panel"' in index
for metric in ("report-pv", "report-self-rate", "report-import", "report-export", "daily-report-notes"):
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
assert 'requestId!==refreshId' in render
assert '.daily-report-kpis' in css and '.preheat-room' not in css

print("PASS: PV & Flex Analysis V2 single-render frontend contract")


