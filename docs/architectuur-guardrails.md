# Architectuur-guardrails

Deze guardrails zijn bindend voor nieuwe functionaliteit, apps, plugins, integraties, actuatorroutes en gegenereerde architectuurdocumentatie binnen het Home Energy Management System (EMS).

## G1 — Native Homey vóór maatwerk

**Geen functie zelf bouwen die Homey betrouwbaar native kan leveren, tenzij onze EMS-semantiek of reproduceerbaarheid een eigen implementatie vereist.**

Bij iedere nieuwe functie geldt daarom deze beslisvolgorde:

1. Controleer of Homey de gevraagde capability betrouwbaar native levert.
2. Hergebruik de native capability wanneer de semantiek, timing, foutafhandeling en reproduceerbaarheid voldoen aan de EMS-eisen.
3. Bouw alleen een eigen implementatie wanneer minimaal één van de volgende punten aantoonbaar geldt:
   - de native Homey-semantiek wijkt af van de gewenste EMS-semantiek;
   - gedrag is niet voldoende deterministisch/reproduceerbaar voor control of regressietests;
   - benodigde state, validiteit, timing of observability ontbreekt;
   - fail-safe/fail-closed gedrag kan niet worden gegarandeerd;
   - de native functie zou de gelaagde architectuur of single-writer-discipline doorbreken.
4. Documenteer bij maatwerk kort waarom native Homey niet voldeed.

### Acceptatiecriterium

Een nieuwe maatwerkfunctie wordt niet als architectuurconform beschouwd wanneer dezelfde functie aantoonbaar betrouwbaar native beschikbaar is en er geen gedocumenteerde EMS-specifieke reden voor maatwerk bestaat.

## G2 — Eén beslisser en één writer per fysieke actuator

**Geen externe app, plugin, flow of integratie mag een tweede beslis- of schrijfpunt naast de Energy Core introduceren.**

Externe componenten mogen in principe:

- meetdata of capabilities leveren;
- events leveren;
- read-only diagnostiek/observability leveren;
- een expliciet gedelegeerde actuatorfunctie uitvoeren wanneer die component de enige writer voor die actuator is.

Externe componenten mogen niet ongemerkt:

- zelfstandig dezelfde fysieke actuator regelen als onze productiewriter;
- een parallelle policy/optimalisatielaag activeren;
- writes uitvoeren op basis van eigen prijs-, PV-, comfort- of laadlogica naast de Energy Core;
- retries of automatische acties uitvoeren die onze idempotency- of lease-semantiek omzeilen.

### Verplichte control-keten

```text
Meetbron / externe app
        ↓
      State
        ↓
   Energy Core
        ↓
 Control intent
        ↓
 exact één writer
        ↓
    actuator
```

Lokale hardwareveiligheid en apparaat-eigen safetyfuncties blijven buiten deze single-writerregel en staan hoger in de veiligheidshiërarchie. Voorbeelden zijn Easee Equalizer en toekomstige Victron ESS/safetyfuncties.

### Acceptatiecriterium

Voor iedere fysiek aangestuurde functie moet in de architectuur eenduidig kunnen worden aangewezen:

- wie de beslisser is;
- wie de enige automatische writer is;
- welke lokale hardwarebeveiliging eventueel autonoom mag ingrijpen.

Wanneer twee softwarecomponenten dezelfde actuator zelfstandig kunnen schrijven, is de integratie **niet architectuurconform** totdat één route read-only is gemaakt of verwijderd.

## G3 — Toets voor nieuwe apps/plugins/integraties

Voor iedere kandidaat-app, plugin of nieuwe integratie wordt vóór productiegebruik minimaal gecontroleerd:

| Vraag | Vereiste |
|---|---|
| Levert Homey dit al betrouwbaar native? | Zo ja: native eerst |
| Is extra EMS-semantiek nodig? | Alleen dan maatwerk |
| Levert de component alleen data/events? | Voorkeur |
| Kan de component zelf actuatoren schrijven? | Expliciet identificeren |
| Ontstaat een tweede controller/writer? | Niet toegestaan |
| Kan automatische retry onze idempotency omzeilen? | Niet toegestaan |
| Is gedrag na reboot/restart reproduceerbaar? | Vereist voor productie |
| Is fail-safe/fail-closed gedrag duidelijk? | Vereist voor control |
| Is de integratie observeerbaar/testbaar? | Vereist voor productie |

## G4 — RC branching en change management

**De gebruiker hoeft bij een wijzigingsverzoek niet zelf aan te geven of de wijziging op `main` of op de actieve RC-branch thuishoort. Branchselectie is onderdeel van de engineeringdiscipline.**

Standaard geldt:

- nieuwe functionaliteit, optimalisaties, refactoring, experimenten, documentatie van toekomstige architectuur en andere niet-noodzakelijke verbeteringen → `main`;
- uitsluitend een defect dat aantoonbaar aanwezig is in de actieve RC én opgelost moet worden voordat die RC naar stable kan promoveren → actieve RC-branch;
- bij twijfel → `main` en de RC blijft ongewijzigd;
- een RC-fix is minimaal, gericht en bevat geen opportunistische refactoring of nieuwe functionaliteit;
- na een RC-fix worden minimaal de geraakte regressie-/RC-criteria opnieuw gevalideerd;
- iedere relevante RC-fix wordt ook teruggebracht naar `main`, zodat de ontwikkellijn de correctie niet verliest;
- wijzigingen aan de RC worden expliciet gemeld voordat ze worden uitgevoerd wanneer uit het verzoek niet reeds ondubbelzinnig blijkt dat het om een release-blocking defect gaat.

### Beslisregel

```text
Wijzigingsverzoek
      │
      ├─ nieuwe feature / verbetering / refactor / experiment? ──► main
      │
      └─ defect in actieve RC?
             │
             ├─ release-blocking en fix nodig vóór stable? ──► RC-fix
             │                                             └──► daarna ook main
             └─ nee / twijfel ─────────────────────────────► main
```

### Acceptatiecriterium

Een wijziging op de RC is alleen toegestaan wanneer kan worden benoemd welk bestaand RC-gedrag defect is, waarom dit promotie naar stable blokkeert en welke gerichte validatie na de fix wordt uitgevoerd. Ontbreekt één van deze drie elementen, dan hoort de wijziging op `main`.

## G5 — Power Intent en actuator-adapters

**Control-policy en fysieke actuatie worden door een harde architectuurgrens van elkaar gescheiden. De Energy Core publiceert apparaat-onafhankelijke power intent; adapters mogen uitsluitend technische uitvoerbaarheid en device-semantiek toevoegen.**

Voor actuator-adapters gelden bindend de volgende regels:

- het upstream control-contract gebruikt functioneel vermogen in watt waar dat fysiek zinvol is; een device-specifieke waarde zoals ampère is geen vervangende Core-policy-interface;
- een adapter mag een target wegens fysieke constraints naar beneden kwantiseren, begrenzen of weigeren, maar mag het upstream toegewezen vermogen nooit verhogen;
- ongeldige, stale of niet-bevestigbare control-input degradeert fail-closed;
- requested, commanded en confirmed actuatorstate worden afzonderlijk gemodelleerd; API-acceptatie telt niet als fysieke bevestiging;
- hoogfrequente runtime-control gebruikt uitsluitend device-interfaces die daarvoor technisch bedoeld zijn; persistente configuratie-/flash-settings zijn geen regelinterface;
- hysterese, PV-smoothing, minimale stabiele duur, prijslogica, opportunity/MUST-keuzes en andere EMS-policy blijven upstream in Energy Core/policy;
- idempotency, dedup, run-lease en rate limiting omringen de writer en worden niet vermengd met de pure intent→device mapping;
- stateful hardwaretransities, waaronder toekomstige 1↔3-faseschakeling, worden als expliciete state machine met bevestiging, dead-time en timeout ontworpen;
- iedere nieuwe LIVE actuator-adapter doorloopt eerst een SHADOW-fase waarin berekende output observeerbaar is terwijl fysieke writes hard uitgeschakeld blijven.

### LIVE release-gate

Een adapter mag niet van SHADOW naar LIVE zolang niet aantoonbaar is bewezen dat:

1. de writer de juiste runtime/dynamic interface gebruikt;
2. stale/invalid input fail-closed afvalt;
3. requested/commanded/confirmed lifecycle observeerbaar en eenduidig is;
4. idempotency, single-writer en restart recovery intact blijven;
5. boundary- en invarianttests aantonen dat de adapter geen upstream power budget kan overschrijden;
6. eventuele stateful actuatortransities expliciet zijn gemodelleerd en getest.

Voor de Easee EV Power Adapter v0.1 betekent dit aanvullend: vaste 3-fase mapping, geen automatische phaseswitching en uitsluitend dynamic/volatile current-control bij een latere LIVE-cut-over.

### Acceptatiecriterium

Een actuator-adapter is niet architectuurconform wanneer hij zelfstandig EMS-policy toevoegt, een upstream power intent kan verhogen, stale data als actueel behandelt, configuratie-instellingen als frequente runtime-write gebruikt of fysieke uitvoering afleidt uit alleen een API-acknowledgement.

## G6 — One-pass architecture document release pipeline

**A request to generate a new software architecture document is treated as one release operation. CI is a verification gate, not the first place where predictable document-generation errors are discovered.**

The standard documentation language is **English**.

Every document release follows this mandatory sequence:

1. **Source refresh** — collect the current architecture, component, Planner, Business Case, adapter, flow and validation sources that belong in the document.
2. **Preflight before build** — validate the manifest, frontmatter, required `sources`, verification dates, expected sections, English publication language and diagram inputs before starting the publication build.
3. **Build** — generate the master publication source, process diagrams, DOCX, real Word table of contents, page numbering and PDF.
4. **Document QA before delivery** — verify the rendered document, not only source text. At minimum confirm:
   - the table of contents contains visible page numbers;
   - document pages have visible page numbering;
   - each process diagram caption uses `Process diagram — <process name>`;
   - the relevant section heading and its process diagram stay on the same page where technically possible;
   - no Mermaid source, generation markers or other implementation artefacts leak into the publication;
   - required current sections such as Planner and Business Case are actually present when applicable.
5. **Artifact-first publication** — DOCX/PDF artefacts are uploaded as soon as they are successfully built. A later supplemental QA check must not make an otherwise generated document inaccessible.
6. **Delivery gate** — only report a document as available after the requested DOCX artefact exists and the mandatory document QA has passed. Intermediate builds are not presented as completed releases.

### Self-testing requirement

Adding a component or section to `manifest.yaml` must be preflight-testable. Missing required metadata such as frontmatter, `sources` or `last_verified` must fail locally/pre-build with a precise diagnostic rather than first being discovered deep inside GitHub Actions.

### Acceptance criterion

A documentation release is conformant only when one invocation can progress from refreshed sources through preflight, build, rendered-document QA and downloadable artefact without manual repair of predictable metadata, TOC, page-numbering, caption or artifact-upload issues.

## Relatie met RC en toekomstige wijzigingen

Deze guardrails veranderen geen bestaande RC-controlpaden op zichzelf. Zij gelden vanaf opname als verplichte architectuurtoets voor nieuwe wijzigingen en voor toekomstige herbeoordeling van bestaande integraties.

Bij iedere relevante architectuurwijziging moeten code, procesflow en documentatie dezelfde control- en writer-eigenaarschap tonen.
