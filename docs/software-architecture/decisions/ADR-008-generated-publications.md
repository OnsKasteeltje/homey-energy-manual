---
title: ADR-008 - DOCX and PDF are generated publication artifacts
date: 2026-08-26
status: accepted
---

# ADR-008 - DOCX and PDF are generated publication artifacts

## Context

Manual edits in Word/PDF cannot be reliably traced back to the architecture sources and are easily lost on regeneration.

## Besluit

DOCX and PDF are generated publication artifacts only. Architectural content is changed in version-controlled source files and regenerated through CI.

## Alternatieven

Maintaining Word as a co-equal source was rejected because it creates bidirectional synchronization and review problems.

## Consequenties

Publication formatting belongs in the build pipeline/templates. Defects in numbering, TOC, pagination or diagrams are fixed in source/build logic rather than in generated documents.

## Validatie / heroverweging

CI regenerates DOCX/PDF and verifies expected headings, TOC and publication integrity.
