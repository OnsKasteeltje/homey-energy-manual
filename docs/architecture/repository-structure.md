# Repository structure and migration policy

## Purpose

This document defines the target repository structure for the EMS project and the migration policy used for every future GitHub change.

The repository has grown organically while the architecture evolved from Homey-centred control toward a split architecture in which the Pi owns planning and orchestration, Homey executes edge control, and the website provides presentation and observability. The repository should increasingly reflect that architecture.

The migration is intentionally incremental. We do **not** perform a risky bulk move of the whole repository. Instead, every future GitHub change must check whether the touched files are already located in the correct target area and move them as part of the same logical change when appropriate.

The governing rule is:

> **Touch it, place it correctly.**

When an existing file is materially changed, its repository location must be evaluated against this target structure. If it is clearly in a legacy or incorrect location, move it to the appropriate target location in the same atomic change, unless doing so would create deployment risk or excessive unrelated churn.

## Target structure

```text
homey-energy-manual/
├── apps/
│   ├── homey/
│   ├── website/
│   └── cloudflare/
│
├── services/
│   └── pi/
│       ├── planner/
│       ├── control/
│       ├── state/
│       ├── api/
│       │   └── status/
│       ├── integrations/
│       │   ├── homey/
│       │   │   ├── ingress/
│       │   │   └── egress/
│       │   ├── tesla/
│       │   ├── easee/
│       │   ├── honeywell/
│       │   ├── connectlife/
│       │   └── energy-prices/
│       └── history/
│
├── deploy/
│   ├── systemd/
│   ├── install/
│   └── migrations/
│
├── config/
│   ├── contracts/
│   ├── devices/
│   └── schemas/
│
├── docs/
│   ├── architecture/
│   ├── components/
│   ├── operations/
│   ├── commissioning/
│   └── decisions/
│
├── tests/
│   ├── planner/
│   ├── control/
│   ├── integrations/
│   └── replay/
│
├── tools/
│   ├── diagnostics/
│   ├── validation/
│   └── maintenance/
│
├── archive/
│   ├── homey-legacy/
│   ├── planner-legacy/
│   └── experiments/
│
├── .github/
└── README.md
```

## Architectural ownership reflected in the repository

The target structure follows the operational ownership model:

- **Homey** is the executor / edge-control layer.
- **Pi** owns planning, orchestration, state processing and external integrations unless explicitly documented otherwise.
- **Homey ↔ Pi integration** lives under `services/pi/integrations/homey/`: ingress describes the Homey-to-Pi state boundary, while egress owns Pi-to-Homey control publication. The HTTP endpoint itself remains under `services/pi/api/` because API transport and integration semantics are separate concerns.
- **Pi API** exposes bounded machine interfaces such as health, state ingest and planner/control status without changing the underlying runtime ownership boundaries.
- **Website** owns presentation and human-facing observability.
- **docs/** contains architecture, component documentation, decisions, commissioning records and operational runbooks, not production runtime implementation.
- **deploy/** contains installation, migration and runtime-service definitions.
- **config/** contains declarative configuration and schemas, not runtime business logic.
- **tests/** contains automated validation, replay and regression artefacts.
- **tools/** contains manually invoked diagnostics, validation and maintenance utilities.
- **archive/** contains intentionally retained legacy implementations and experiments that are no longer part of production.

## Mandatory placement rules

### 1. Production code must live outside documentation

Production runtime code must not be introduced under `docs/`, temporary folders, commissioning evidence directories or generated-data locations.

### 2. New files use the target structure immediately

Every new source, test, deployment, configuration or documentation file must be placed directly in the appropriate target area.

Do not create new legacy top-level locations merely because a related older file still lives there.

### 3. Touch it, place it correctly

Every GitHub action that materially changes an existing file must include a placement check:

1. What architectural component owns this file?
2. Is its current path consistent with the target structure?
3. If not, can it safely be moved as part of this same logical change?
4. If not moved now, document why the legacy path must temporarily remain.

A file does not need to move for a typo-only edit, generated-data refresh or similarly trivial change where relocation would create disproportionate churn.

### 4. Replacement handling

When functionality is replaced:

- delete obsolete code when Git history is sufficient and no rollback need remains;
- move deliberately retained historical code to `archive/` when it still has operational, diagnostic or learning value;
- keep rollback code outside `archive/` only when it is still an intentionally supported rollback path;
- mark supported rollback paths clearly in documentation and naming.

### 5. TEMP, HOTFIX and SHADOW are lifecycle states, not permanent locations

Files or scripts labelled `TEMP`, `HOTFIX`, `SHADOW`, `TEST`, `commissioning` or similar must have an explicit lifecycle decision when next touched:

- promote to production and place correctly;
- retain as validation/test code under `tests/` or `tools/`;
- archive;
- delete.

They must not silently accumulate in active production directories.

### 6. Moves must preserve atomic architecture changes

A relocation that accompanies an architecture-sensitive implementation change belongs in the same atomic commit as:

- the implementation change;
- updated imports, service paths and deployment references;
- tests and fixtures;
- required canonical architecture documentation updates.

A moved file must never leave `main` temporarily broken between commits.

### 7. Generated/runtime data is not source architecture

Generated website JSON, runtime snapshots, evidence exports and similar artefacts must be clearly separated from canonical implementation and documentation. Their presence must never determine architectural ownership.

## Migration strategy

The repository will converge gradually rather than through one large reorganisation.

For each future change:

1. identify all files that are materially touched;
2. classify each as production, rollback, test/validation, tooling, documentation, configuration, generated data or legacy;
3. compare its current path with the target structure;
4. move incorrect paths when safe and proportionate;
5. update all references atomically;
6. verify runtime/deploy/test behaviour;
7. commit the logical change as one internally consistent unit.

This makes normal development itself the migration mechanism.

## Cleanup classifications

Repository cleanup uses these classifications:

- **KEEP / PRODUCTION** — active runtime, deploy, website, configuration or canonical documentation.
- **ROLLBACK** — intentionally supported fallback path; retained and clearly labelled.
- **ARCHIVE** — no longer production, but intentionally retained for history, diagnostics or learning.
- **DELETE CANDIDATE** — no active dependency and no justified rollback/archive value.

No file should be deleted solely because its name looks old. Dependency checks must include imports, systemd units, deployment scripts, workflows, documentation references, website references and relevant Pi/Homey runtime contracts.

## Definition of done for future GitHub changes

A GitHub change is not complete until all of the following are true where applicable:

- implementation works;
- tests/validation are updated;
- architecture documentation is updated;
- deployment references remain valid;
- touched files have passed the repository-placement check;
- newly obsolete files have an explicit keep/rollback/archive/delete decision;
- no unnecessary TEMP/HOTFIX/SHADOW artefacts are left behind;
- the resulting commit is internally consistent and deployable.

## Relationship to existing architecture governance

This policy complements `CONTRIBUTING.md` and the architecture governance documents. It does not override the existing atomic-change requirement. Repository relocation is part of architecture hygiene and must obey the same atomicity and deployment-safety rules.
