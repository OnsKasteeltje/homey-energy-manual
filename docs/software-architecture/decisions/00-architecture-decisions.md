---
title: Architecture Decisions
version: 0.1
status: active
architecture_status: implemented
last_verified: 2026-08-26
source:
  - docs/software-architecture/decisions/ADR-001-markdown-source-format.md
  - docs/software-architecture/decisions/ADR-002-implementation-authoritative.md
  - docs/software-architecture/decisions/ADR-003-generated-process-diagrams.md
  - docs/software-architecture/decisions/ADR-004-power-intent-contract.md
  - docs/software-architecture/decisions/ADR-005-adapters-no-ems-policy.md
  - docs/software-architecture/decisions/ADR-006-single-writer.md
  - docs/software-architecture/decisions/ADR-007-shadow-before-active.md
  - docs/software-architecture/decisions/ADR-008-generated-publications.md
---

# Architecture Decisions

De architectuur gebruikt Architecture Decision Records (ADR's) om besluiten duurzaam naast code en documentatie vast te leggen. Een ADR beschrijft context, besluit, alternatieven, consequenties en validatie/heroverweging.

De huidige accepted baseline bevat de volgende besluiten:

- ADR-001 — Markdown is the architecture source format.
- ADR-002 — Implementation is authoritative over documentation.
- ADR-003 — Process diagrams are generated from the process model.
- ADR-004 — Power Intent is the only upstream power-control contract.
- ADR-005 — Device adapters contain no EMS policy.
- ADR-006 — Single writer per physical device.
- ADR-007 — SHADOW before ACTIVE.
- ADR-008 — DOCX/PDF are generated publication artifacts.

Nieuwe architectuurbesluiten worden als afzonderlijke ADR toegevoegd; bestaande ADR's worden niet stil herschreven wanneer de beslissing inhoudelijk verandert, maar waar nodig superseded door een nieuwe ADR.
