# EMS Live V0.4 — single-screen bidirectional observability

Status: implemented in source for guarded release; not automatically installed on Pi.

## Visual contract

At desktop width >= 1440 px and height >= 900 px, use a compact 2x2 CSS grid:
energy-flow diagram top-left (~8/12); AlphaESS top-right (~4/12);
active consumers bottom-left (~7/12); signed P1 phase/net details bottom-right
(~5/12). One-screen without vertical scroll is the target; 1366x768 is also
a supported design target subject to real Safari validation. Narrow viewports
(< 1051 px) are allowed to stack and scroll.

This diagram is a *topology*, not a power-conserving Sankey model. PV and net
are on the left, a visually central energy hub connects to Tesla, heat, warm
water (when active) and Other on the right. AlphaESS is an independent neutral
bidirectional connector below the hub; its read-only telemetry is also shown
in the separate right-side panel from the same API, never double counted.

## Source / quality contract

- P1 signed power from /web/state/current remains authoritative for NET:
  positive = import with →; negative = export with ←; zero = balanced ↔;
  missing or failed P1 freshness gate = unknown/neutral, no power assertion.
  Each phase shows only its signed net P1 power when the gate is valid.
- PV total is rendered only when all three sources are reliably fresh as
  MEASURED, preserving per-source detailed evidence on hover/focus. Partial
  PV sources may be shown individually in the popover but never fabricated as
  a complete aggregated power or PV-to-house allocation.
- The pre-existing browser-side estimate of house power, PV + signed P1, does
  not account for an AC-coupled storage device behind P1. Until battery energy
  and AC sign semantics are validated, V0.4 explicitly displays House — and
  Other —. No battery correction, invented residual, PV self-consumption
  percentage, per-appliance power or flow conservation is claimed.
- AlphaESS /web/live/battery is separate and read-only; only a complete
  fresh 300-second-validity raw record is live. Display the signed observed
  AC wattage with neutral ↕ link (direction unverified), SOC and cumulative
  battery counters with caveats. Never use it as an EMS controller, grid
  correction, household balance or net AC-energy counter.
- Tesla/heat/WW retain their independent allowed current-state evidence;
  appliance statuses remain direct or fingerprinted, not measured device W.
- Detailed data warnings stay accessible by keyboard through native disclosure
  widgets. Unknown/stale values display —, never a fabricated zero.

## Components and release boundary

- New frontend/live/index.html 2x2 Live DOM.
- New frontend/live/styles/live-v04.css additive overlay; preserve live.css.
- New frontend/live/state/flow-v04.mjs pure presentation projection.
- Existing frontend/live/render/live.js uses the new projection, preserving
  P1, inverter provenance, phase and appliance diagnostics.
- Existing frontend/live/render/battery.mjs populates the neutral flow node
  from the same independent battery API response.
- No Web Data API change, no Homey/EMS controller/BMS/AlphaESS timer change,
  no Caddy change, no new public listener. Caddy static content is no-store.
- A narrow frontend-only installer defaults to preflight, requires clean synced
  main, checks the pinned V0.3 deployed file baseline, runs tests, validates
  both read-only APIs and only copies the changed Live files on --apply.
  It backups touched files and has targeted rollback; no service restarts.

## Acceptance

Pass architecture and security workflows, JS and asset regressions, bidirectional
P1 tests, partial-PV quality tests, unknown house/residual contract, and
separate AlphaESS stale/read-only tests. Inspect the deployed page on real
Safari at 1440x900 and 1366x768, including PV=2/3 and net export,
and confirm no vertical scrolling or clipping at the design targets.
Narrow/mobile view may reflow and scroll; reduced-motion preference honored.
The Energy Today tab is deliberately out of scope until verified
battery-aware energy accounting is available.
