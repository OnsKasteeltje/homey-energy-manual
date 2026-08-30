<h1>Planner Shadow</h1>

<!--
PLANNER TIMELINE SYNCHRONIZATION INVARIANT — MUST NOT REGRESS

All time-based visualizations on the Planner page MUST use one identical horizontal
time geometry for the same 96 x 15-minute planning slots. This includes at least:
- 24-hour energy-balance chart;
- price chart;
- Tesla action timeline;
- warm-water / boiler action timeline;
- battery action timeline and any future planner action row.

Required invariant:
1. Slot i MUST occupy the same horizontal pixel interval in every Planner timeline.
2. All timelines MUST have the same plot origin, plot width and 96-column scale.
3. Y-axis labels, asset labels, wrappers, margins and gaps MUST sit outside the shared
   plot geometry and MUST NOT alter the slot origin or scale.
4. A frontend change to axes, wrappers, labels, margins, responsive layout or action
   rows MUST be treated as a timeline-sync regression risk.
5. Acceptance test after such a change: compare at least two known timestamps and one
   multi-slot action against both charts; their slot boundaries MUST align visually.
6. There MUST be only one active owner for Planner axis wrapping/decorating. Legacy
   decorators must not wrap the same chart a second time.
7. Boiler planning has one visual owner only: the primary Boiler action row. Explanatory
   decorators may enrich that row but MUST NOT create a second Boiler timeline.

This synchronization is a Planner UI architecture invariant, not a cosmetic preference.
-->

<link rel="stylesheet" href="../stylesheets/planner-axes-v1.1.0.css">
<link rel="stylesheet" href="../stylesheets/planner-ww-multislot-v1.1.0.css?owner=10">
<link rel="stylesheet" href="../stylesheets/planner-device-tabs-v1.0.0.css">

<div id="planner-shadow" class="planner-shadow" data-source="https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow.json?source=planner-shadow" data-history="../data/energy-day-series-7d.json">
  <div class="ps-hero">
    <div>
      <div class="ps-kicker">EMS → doel</div>
      <h2>24-uurs planner</h2>
      <p>Wat besluit het EMS, wanneer en waarom?</p>
    </div>
    <div class="ps-mode"><strong>SHADOW</strong><span>geen fysieke aansturing</span></div>
  </div>

  <div class="admonition info" style="margin-top:1rem">
    <p class="admonition-title">Fasetopologie voor volgende Planner-optimalisatie</p>
    <p><strong>Boiler = L2</strong> is op 30 augustus 2026 empirisch gevalideerd met meerdere onafhankelijke ON/OFF-flanken tegenover P1-fasevermogen. De boiler is een éénfasebelasting van circa <strong>1,9–2,0 kW / ~8,5 A op L2</strong>. Tesla/Easee is 3-fase. Deze topologie wordt de basis voor de volgende Planner-iteratie met <strong>phase-aware 3×25 A headroom</strong>; die headroomlogica is nog niet actief.</p>
    <p><small>Machineleesbare bron: <code>docs/data/ems-phase-topology.json</code>. Planner blijft tot die volgende iteratie expliciet <code>NOT_MODELED_PHASE_AWARE</code>.</small></p>
  </div>

  <div id="ps-status">Plannerdata laden…</div>
</div>
