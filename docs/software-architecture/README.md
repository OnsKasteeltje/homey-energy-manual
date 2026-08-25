# Software Architecture Documentation Framework

Deze map is de primaire, versiebeheerbare bron voor de softwarearchitectuur van het Home Energy Management System (HEMS).

## Doel

De softwaredocumentatie wordt niet langer primair als handmatig Word-document onderhouden. De inhoud wordt modulair vastgelegd in Markdown en kan daaruit reproduceerbaar worden samengesteld tot één masterdocument en vervolgens DOCX/PDF.

## Bronnen van waarheid

1. De actuele implementatie in code/configuratie is leidend.
2. Markdown beschrijft uitsluitend de aantoonbaar geïmplementeerde of expliciet als SHADOW gemarkeerde situatie.
3. Procesdiagrammen moeten overeenkomen met de actuele code/configuratie en worden bij relevante codewijzigingen opnieuw gevalideerd.
4. `generated/` bevat afgeleide output en wordt niet handmatig bewerkt.

## Structuur

- `architecture/` — systeemcontext, principes, datamodel en generieke architectuur.
- `components/` — componentbeschrijvingen volgens één vast sjabloon.
- `flows/` — procesflows en state machines, bij voorkeur in Mermaid.
- `validation/` — teststrategie, RC-criteria, runtime-validaties en bekende beperkingen.
- `decisions/` — Architecture Decision Records (ADR's).
- `templates/` — verplichte sjablonen.
- `manifest.yaml` — volgorde en selectie voor het samengestelde masterdocument.
- `generated/` — automatisch gegenereerde masterdocumenten/artifacts.

## Verplichte componentsecties

Iedere componentbeschrijving gebruikt dezelfde volgorde:

1. Doel
2. Scope
3. Inputs
4. Outputs
5. State model
6. Beslislogica
7. Procesflow
8. Foutafhandeling
9. Idempotency
10. SHADOW/ACTIVE-status
11. Validatie
12. Bekende beperkingen
13. Bronbestanden

## Documentatiestatus

Gebruik in YAML-frontmatter minimaal:

- `component`
- `title`
- `version`
- `status`: `draft`, `shadow`, `active`, `deprecated`
- `architecture_status`: `planned`, `implemented`, `validated`
- `last_verified`
- `source`

`last_verified` betekent: inhoud en diagrammen zijn op die datum gecontroleerd tegen de genoemde bronbestanden en actuele runtime-/configuratiestatus.

## Wijzigingsregel

Een relevante wijziging aan een component is pas documentatie-compleet wanneer:

- de component-Markdown is gecontroleerd/bijgewerkt;
- relevante Mermaid-flow/state machine is gecontroleerd tegen de code;
- `last_verified` is bijgewerkt;
- validatie of bekende beperking is toegevoegd wanneer gedrag nog niet volledig runtime-gevalideerd is.

## Migratie

Bestaande pagina's onder `docs/` blijven voorlopig intact. Inhoud wordt stapsgewijs naar deze structuur gemigreerd. Pas nadat een onderwerp inhoudelijk is gecontroleerd tegen de actuele implementatie wordt de nieuwe module als architectuurbron beschouwd.
