# Process Model Standard

Procesdiagrammen onder `docs/software-architecture/flows/` worden niet handmatig als Mermaid onderhouden.

De bron is een fenced `process-model` JSON-blok. De generator `scripts/generate_process_diagrams.py` schrijft het bijbehorende Mermaid-blok tussen `GENERATED_MERMAID:<id>` markers.

Ondersteunde vormen:

1. Semantisch model met `nodes` en `edges` — voorkeursvorm voor nieuwe of inhoudelijk gewijzigde flows.
2. `kind: mermaid-source` — migratievorm voor bestaande gevalideerde diagrammen. Hierbij is het machineleesbare process-model de enige bron; het Mermaid-blok blijft generated content.

CI voert twee guards uit:

- `scripts/migrate_legacy_mermaid.py --check` faalt als een handmatig Mermaid-blok buiten generated markers wordt toegevoegd.
- `scripts/generate_process_diagrams.py --check` faalt als generated Mermaid afwijkt van het process-model.

Bij inhoudelijke aanpassing van een gemigreerde `mermaid-source` flow verdient omzetting naar het semantische `nodes`/`edges` model de voorkeur. Nieuwe beslislogica wordt direct als semantisch model toegevoegd en niet eerst als handmatig Mermaid-diagram.
