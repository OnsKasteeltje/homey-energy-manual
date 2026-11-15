# EMS Frontend V2 — Universal Popup Positioning V1.0

## Status and scope
Architecture guardrail for **every** interactive floating surface in the private EMS V2 frontend (Live, Invoer, Historie, Planner, Evaluatie/PV Flex, Verwarming, AI Analyse and future pages). Covers tooltips, detail popovers, dropdowns and contextual panels. Modal dialogs remain governed by separate focus-trap/modal rules. No changes to Pi, Homey, Easee, planning or data quality.

## Normative rules (MUST)
1. One shared popup manager owns popup lifecycle and viewport positioning; features own only content, trigger and semantics. No card-level hard-coded popup coordinates, per-feature viewport calculations, or CSS-only hover positioning.
2. Popups are rendered in a **body-level overlay layer**, outside scrolling or clipped dashboard cards. Never relax unrelated card overflow settings to compensate.
3. Placement measures the trigger, content dimensions and current viewport. It prefers below, flips to a fitting side (above/right/left), then clamps against all viewport edges with an explicit safe margin. Constrain oversized content and allow internal scrolling, including at browser zoom and small screens.
4. Reposition on scroll, resize, anchor resize and content resize. If the anchor disappears, dismiss the popup. Escape and outside-click dismiss it; preserve keyboard navigation and focus interaction.
5. Appropriate trigger semantics are required (focusable element, aria-describedby for informational tooltip, aria-expanded/controls for interactive panels). Never rely exclusively on hover. Responsive adaptation may use a bottom sheet for extensive touch content, via the same manager, not custom card scripts.
6. Assets are local on the Pi private site; no runtime CDN, public domain, external UI/analytics calls or extra browser-to-Pi command routes. A positioning library such as Floating UI may replace the calculation engine only when bundled locally and vetted; the central contract remains identical.
7. Do not change user-visible energy figures, precision, freshness/quality semantics, API or actuator ownership. Popups are presentation-only and may not trigger EMS writes.

## Implementation and migration
Canonical shared module: `frontend/shared/popup-manager.mjs`; stylesheet: `frontend/shared/styles/popup-manager.css`.
Opt-in trigger contract: `data-ems-popup-anchor="<popup-id>"`. Popup element retains its ID, role and markup. The manager portals the popup to `document.body` while active, and restores it on close. Load the shared module once on any page with floating UI.

Initial migration: Live PV inverter-source tooltip `pv-source-popover`. Further existing popups MUST be inventoried and migrated incrementally; adopting the shared module on one page does **not** establish sitewide migration completion.

## Regression / release guardrails
- Geometry tests: top/bottom/right/left edges, tiny viewports, oversized popups, zoom/resize, nested overflow and scrolling.
- Interaction tests: keyboard focus, Escape, pointer crossing trigger/popup, outside-click, scroll, touch, dynamic content and ARIA.
- A frontend change creating or editing a popup MUST use the shared manager and add relevant tests. A reviewer MUST reject new per-card fixed-position popup logic.
- Before promoting to Pi: targeted frontend tests, repository validation, architecture gate, asset-path validation, private Caddy/Tailscale checks and browser screenshot on desktop/mobile. GitHub merge does not equal Pi runtime deployment.
- No new services, API endpoints or public access. Roll back by restoring frontend assets only; do not touch Pi authority or Homey execution.

## Evidence / limitations
The 2026-11-15 Live PV screenshot showed a tooltip overflowing the usable viewport. Existing CSS anchored `.pv-source-popover` below the PV card without flipping or edge collision checks. V1 provides a shared local positioning mechanism and migrates this first instance. Broader cross-page migration and visual browser QA remain explicit acceptance work, not assumed complete.
