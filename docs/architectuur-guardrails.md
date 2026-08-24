# Architectuur-guardrails

Deze guardrails zijn bindend voor nieuwe functionaliteit, apps, plugins, integraties en actuatorroutes binnen het Home Energy Management System (EMS).

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

## Relatie met RC en toekomstige wijzigingen

Deze guardrails veranderen geen bestaande RC-controlpaden op zichzelf. Zij gelden vanaf opname als verplichte architectuurtoets voor nieuwe wijzigingen en voor toekomstige herbeoordeling van bestaande integraties.

Bij iedere relevante architectuurwijziging moeten code, procesflow en documentatie dezelfde control- en writer-eigenaarschap tonen.
