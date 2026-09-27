from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "frontend/heating/index.html"
RENDER = ROOT / "frontend/heating/render/heating.js"
STYLE = ROOT / "frontend/heating/styles/heating.css"


def test_heating_page_is_heating_only_analysis_surface():
    index = INDEX.read_text()
    render = RENDER.read_text()

    assert "Temperatuur &amp; voorverwarming" in index
    assert "Heating Flex observability" not in index
    assert '"/web/heating/schedule"' in render
    assert '"/web/heating/temperature-history"' in render
    assert '"/web/planner/heating-preheat-shadow"' in render
    assert '"/web/planner/heating-preheat-progression-shadow"' in render

    # Heating page must not become a second PV/flex or EV analysis surface.
    assert "/web/analysis/pv-flex/" not in render
    assert "/web/planner/pv-forecast" not in render
    assert "/web/planner/ev-requirement" not in render


def test_heating_chart_keeps_authority_observation_shadow_distinct():
    index = INDEX.read_text()
    render = RENDER.read_text()
    style = STYLE.read_text()

    assert "Honeywell baseline" in index
    assert "werkelijke kamertemperatuur" in index
    assert "EMS preheat shadow" in index

    assert "baseline-line" in render
    assert "actual-line" in render
    assert "shadow-target" in render
    assert "preheat-window" in render

    assert ".baseline-line" in style
    assert ".actual-line" in style
    assert ".shadow-target" in style
    assert ".preheat-window" in style


def test_heating_ui_does_not_invent_historical_shadow_events():
    render = RENDER.read_text()

    # Current V0.4 state may be shown from activeStepStartedAt to now only.
    assert "activeStepStartedAt" in render
    assert "minuteAt(now,start)" in render
    assert "historicalShadow" not in render


def test_heating_renderer_contains_no_literal_source_newline_escape():
    render = RENDER.read_text()
    assert r"\nconst " not in render


def test_heating_hover_is_bound_to_individual_lines():
    render = RENDER.read_text()
    style = STYLE.read_text()

    assert "hoverTargets" in render
    assert 'class:"line-hit"' in render
    assert "showTarget(event,target)" in render
    assert 'const hit = add("rect"' not in render
    assert "crosshair" not in render

    assert ".line-hit" in style
    assert "pointer-events:stroke" in style
    assert ".hover-marker" in style


def test_heating_tooltip_shows_one_room_and_one_signal():
    render = RENDER.read_text()

    assert 'label = "Honeywell baseline"' in render
    assert 'label = "Gemeten temperatuur"' in render
    assert 'label = "EMS shadow-target"' in render
    assert 'class="tip-line"' in render
    assert 'visible.map(room =>' not in render


def test_preheat_window_is_rendered_only_for_eligible_up_transition():
    render = RENDER.read_text()

    assert 'candidate?.status === "ELIGIBLE_UP_TRANSITION"' in render
    assert "hasEligiblePreheatWindow(candidate)" in render
    assert 'const windowText = hasEligiblePreheatWindow(candidate)' in render
    assert 'if(hasEligiblePreheatWindow(candidate))' in render
    assert 'if(candidate?.opportunityOpensAt && candidate?.opportunityClosesAt)' not in render
