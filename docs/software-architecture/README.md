# Software Architecture Documentation Framework

Deze map is de primaire, versiebeheerbare bron voor de modulaire softwarearchitectuur van het Home Energy Management System (HEMS).

## Doel

De softwaredocumentatie wordt niet langer primair als handmatig Word-document onderhouden. De inhoud wordt modulair vastgelegd in Markdown en kan daaruit reproduceerbaar worden samengesteld tot één masterdocument en vervolgens DOCX/PDF.

## Bronnen van waarheid

1. De actuele implementatie in code/configuratie en de live gevalideerde Homey/Pi-runtime zijn leidend.
2. `docs/architecture/CURRENT-EMS-STATE.md` is het canonieke current-state document voor de operationele Homey/Pi architectuur.
3. De documenten onder `docs/software-architecture/` detailleren die architectuur per component en proces en mogen niet in strijd zijn met de canonical current state.
4. Markdown beschrijft uitsluitend aantoonbaar geïmplementeerde functionaliteit of markeert SHADOW/rollback/planned expliciet.
5. Procesdiagrammen moeten overeenkomen met actuele code/configuratie en worden bij relevante architectuurwijzigingen opnieuw gevalideerd.
6. `generated/` bevat afgeleide output en wordt niet handmatig bewerkt.

Bij conflict geldt de volgorde:

`live gevalideerde implementatie -> CURRENT-EMS-STATE.md -> component/flow Markdown -> generated output -> historische DOCX/PDF baseline`.

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

Iedere componentbeschrijving gebruikt waar praktisch dezelfde volgorde:

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
- `version` waar relevant
- `status`: `draft`, `shadow`, `active`, `deprecated`
- `architecture_status`: bijvoorbeeld `planned`, `implemented-shadow`, `implemented-production`, `validated`
- `last_verified`
- `source`

`last_verified` betekent: inhoud en diagrammen zijn op die datum gecontroleerd tegen de genoemde bronbestanden én de actuele runtime-/configuratiestatus.

## Wijzigingsregel

Een architectuurrelevante wijziging is pas documentatie-compleet wanneer:

- `docs/architecture/CURRENT-EMS-STATE.md` is gecontroleerd/bijgewerkt wanneer responsibility, authority, contractpolicy, runtime/service of physical-writer boundary verandert;
- de relevante component-Markdown is gecontroleerd/bijgewerkt;
- relevante Mermaid-flow/state machine is gecontroleerd tegen de implementatie;
- `last_verified` is bijgewerkt;
- validatie of bekende beperking is toegevoegd wanneer gedrag nog niet volledig runtime-gevalideerd is;
- SHADOW/rollback/TEMP-functionaliteit niet als productiepad wordt afgebeeld.

## Driftregel

Vastgestelde documentatiedrift wordt niet opgelost door de actuele implementatie terug te interpreteren naar de oude tekst. De documentatie wordt gecorrigeerd naar de aantoonbare as-built situatie, tenzij expliciet is besloten de implementatie terug te draaien.

Historische baselines blijven als historie bruikbaar, maar mogen niet als actuele runtimebron worden geciteerd wanneer nieuwere as-built documentatie beschikbaar is.

## Migratie

Bestaande pagina's onder `docs/` blijven waar nodig als historie of aanvullende context bestaan. Een onderwerp wordt pas als actuele architectuurbron beschouwd nadat het tegen de implementatie en canonical current-state documentatie is gecontroleerd.
