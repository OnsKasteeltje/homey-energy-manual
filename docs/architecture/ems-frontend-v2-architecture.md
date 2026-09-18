# EMS Frontend V2 Architecture Contract

Status: **TARGET / migration contract**  
Date: 2026-09-18

## 1. Purpose

Frontend V2 is a clean-room replacement for the organically grown MkDocs frontend. It reuses proven EMS data contracts and selected domain logic, but does not inherit the legacy renderer/patch stack.

The existing site remains available as a reference during migration. A page is cut over only after its V2 replacement has been validated.

## 2. Architectural role

Frontend V2 follows the canonical EMS governance:

- **Pi** owns planning and optimization.
- **Homey** owns realtime state, safety and execution.
- **Frontend** owns presentation and explicit user command input only.
- **GitHub** is canonical for software and documentation, not realtime state transport.

Frontend code MUST NOT introduce EMS optimization, actuator ownership or hidden control policy.

## 3. Page scope

The target navigation contains:

1. **Live** — observation only; realtime energy/state presentation.
2. **Invoer** — explicit user command input for:
   - energy contract;
   - warm-water source;
   - Tesla deadline, target SOC and maximum charging current.
3. **Energiehistorie** — only the compact history dashboard:
   - Dag / Week / Maand / Jaar;
   - KPI summary;
   - date navigation;
   - energy graph.
4. **Planner** — preserved functionally and visually during the first migration phase.
5. **Groepen & fasen** — preserved functionally and visually during the first migration phase.

The current **Home** page has no V2 successor and is removed at final cutover.

## 4. Clean-room rule

V2 imports **behaviour and contracts, not legacy render layers**.

Legacy files may be read to identify:
- canonical input fields;
- validated calculations;
- command/write interfaces;
- safety/freshness semantics;
- desired visual behaviour.

V2 MUST NOT reproduce a chain of primary renderer + decorator + corrective renderer + compatibility patch for the same component.

## 5. Ownership invariants

For every visible component there MUST be exactly one render owner.

For every user-editable setting there MUST be exactly one UI controller owner.

A renderer:
- receives normalized state;
- renders only its own page/component;
- MUST NOT mutate canonical EMS state;
- MUST NOT patch DOM owned by another renderer.

A state adapter:
- reads/parses a defined source;
- normalizes data;
- MUST NOT render DOM.

A controller:
- handles explicit user input;
- writes only through the documented command interface;
- MUST NOT contain EMS optimization policy.

## 6. Target source structure

New or migrated frontend source belongs under:

```text
frontend/
├── shared/
│   ├── state/
│   ├── formatting/
│   └── shell/
├── live/
│   ├── state/
│   ├── render/
│   └── styles/
├── settings/
│   ├── state/
│   ├── render/
│   ├── control/
│   └── styles/
└── history/
    ├── state/
    ├── render/
    └── styles/
```

Planner and Groepen & fasen stay on their current implementation until their own controlled migration.

Build/deployment tooling may live outside `frontend/` where repository conventions require it, but V2 page source MUST NOT be added back to `docs/javascripts/` or `docs/stylesheets/`.

## 7. Repository migration rule

**If you touch it, you move it.**

When legacy frontend source is functionally changed, it MUST be migrated to its canonical V2 location in the same change set. Do not create another numbered patch/version beside the legacy file.

Reading a legacy file for reference does not trigger migration.

When a V2 page replaces a legacy page:
1. prove no remaining active dependency on page-only legacy assets;
2. switch the route/build to V2;
3. remove obsolete page-only renderers/styles rather than moving them.

## 8. Loading and bundle rules

The legacy global bundle is not the V2 target.

V2 uses:
- a minimal shared asset set;
- page-specific assets loaded only for the page that owns them.

Live code MUST NOT load on History merely because both are frontend pages. Settings controllers MUST NOT load on Live. Homepage-only code has no place in V2.

Planner and Groepen & fasen may temporarily retain legacy loading dependencies until their later migration; this exception MUST NOT be used to add new V2 logic to the legacy global bundle.

## 9. State and data rules

Each page has one normalized page-state boundary:

```text
canonical source
      ↓
state adapter
      ↓
normalized page state
      ↓
single render owner
      ↓
DOM
```

Presentation fallbacks must remain presentation-only. Unknown/null source values MUST NOT silently become physical zero values unless the canonical source contract explicitly defines that semantic.

Time display uses Europe/Amsterdam for user-facing local times while preserving canonical timestamps internally.

## 10. Migration sequence

1. Establish V2 architecture and build skeleton.
2. Build **Live V2** read-only.
3. Validate Live V2 against canonical state and current visual behaviour.
4. Build **Invoer V2** and validate command interfaces independently.
5. Build reduced **Energiehistorie V2**.
6. Remove Home route/page.
7. Cut over validated V2 pages and delete their obsolete legacy-only layers.
8. Migrate Planner later as a separate change.
9. Migrate Groepen & fasen later as a separate change.

No big-bang replacement is required.

## 11. Validation / Definition of Done

Every V2 cutover change requires:

- **IMPLEMENTATION PASS**
- **RUNTIME VALIDATION PASS**
- **GITHUB SOURCE SYNC PASS**
- **ARCHITECTURE DOCUMENTATION PASS**

Frontend-specific validation additionally proves:
- one render owner per visible component;
- no cross-page DOM mutation;
- no hidden Homey/device polling introduced by page visits;
- no EMS optimization/control policy moved into frontend;
- page-specific code is not globally loaded without documented reason;
- Planner and Groepen & fasen remain unchanged while frozen.

## 12. First implementation boundary

The first implementation is **Live V2**.

It is read-only and may reuse canonical field semantics and validated calculations from the current Live implementation. It must be implemented as a new single-owner V2 render chain rather than by modifying or stacking onto the current `live-energy-*` render layers.


## 13. Invoer V2 — explicit command semantics

Invoer V2 MUST make a strict visual and semantic distinction between **observed/current state** and **user-entered command values**.

For Tesla deadline input in particular:

- `Huidige SOC` and `Doel-SOC` MUST NOT mix placeholder semantics and persisted/input-value semantics in visually indistinguishable fields.
- A visible number in an editable field MUST have one unambiguous meaning: either it is the actual command value that will be submitted, or it is clearly styled and labelled as non-submitted reference information.
- Current/observed SOC SHOULD be presented separately from the editable command fields when this removes ambiguity.
- Typing into an empty command field MUST behave as normal replacement/input; a user MUST NOT need to know whether an existing-looking number is a placeholder or a real value.
- Before submission, the UI MUST make the complete command unambiguous: local deadline time, current SOC used for the command, target SOC and maximum charging current.
- After a successful write, the UI MUST show the exact accepted command, for example: `Deadline 21:57 · 21% → 40% · max 10 A`.
- User-facing deadline times are entered and confirmed in Europe/Amsterdam local time; canonical timestamps may remain UTC internally.
- The command interface MUST be validated independently before Invoer V2 replaces the legacy Tesla input.

The legacy Tesla input is intentionally not modified solely to correct this usability issue; the requirement is carried into the clean-room Invoer V2 implementation to avoid adding another compatibility patch to the legacy frontend.
