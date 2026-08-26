---
title: ADR-001 - Markdown is the architecture source format
date: 2026-08-26
status: accepted
---

# ADR-001 - Markdown is the architecture source format

## Context

The HEMS documentation is maintained as Docs-as-Code and must remain diffable, reviewable and reproducible in Git.

## Besluit

Markdown is the authoritative human-readable source format for software architecture documentation. DOCX, PDF and website output are derived artifacts.

## Alternatieven

AsciiDoc/docToolchain was considered, but would add a second source format and migration burden without replacing the HEMS-specific build and QA already present.

## Consequenties

Architecture changes are reviewed through Git. Generated artifacts are never edited as source.

## Validatie / heroverweging

The architecture build must assemble Markdown successfully and regenerate publication artifacts deterministically.
