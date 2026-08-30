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

This synchronization is a Planner UI architecture invariant, not a cosmetic preference.
-->

<link rel="stylesheet" href="../stylesheets/planner-axes-v1.1.0.css">
<link rel="stylesheet" href="../stylesheets/planner-ww-multislot-v1.0.0.css">
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
  <div id="ps-status">Plannerdata laden…</div>
</div>
