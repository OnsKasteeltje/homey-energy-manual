# Architectuuroverzicht

> **Current-state authority:** actuele procesflows en statusclaims op deze pagina moeten worden gelezen tegen `docs/architecture/homey-runtime-baseline-2026-08-30.md` en `docs/architecture/current-runtime-source-policy.md`. Voor Core is `src/homey/core/core-v0.11f.live-homey.js` de exacte actuele bron. Historische candidate/patch/smoke/rollback-bestanden zijn geen huidige architectuur.

Deze pagina beschrijft de **actuele gecodeerde architectuur van Energy Core v2**. Procesflows en statusbeschrijvingen moeten overeenkomen met de productiecode; toekomstige of historische architectuur wordt expliciet gemarkeerd.

## 1. Hoofdstructuur

```text
FYSIEKE INSTALLATIE / VEILIGHEID
3×25 A · P1 · Easee Equalizer · lokale apparaatbeveiligingen
                    │
                    ▼
               METEN / STATE
P1 · PV · Easee · boiler · Quatt · relevante devices
                    │
                    ▼
        ENERGY CORE v2 — v0.11f / 5 min
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
      State      Decision     Shadow
                    │
             realtime intents
                    │
                    ▼
        afzonderlijk gevalideerde writers

Ondersteunende planningslaag:
Contract-/prijscontext · Tesla/WW-verplichtingen · PV-context
                    │
                    ▼
  24h Energy Planner v0.4.9 SHADOW LOW-LOAD
                    │
                    ▼
        plan/intents · geen fysieke writes
```

De Energy Manager ligt niet in het fysieke stroompad. Installatieveiligheid, lokale apparaatbeveiligingen en Easee Equalizer blijven hoger in de hiërarchie.

## 2. Core en Homey-belasting

De actuele Core is `EM v2 | 00 Core Tick | v0.11f (Planner Tesla Headroom)` en draait iedere vijf minuten plus handmatige start. De exacte runtime staat in `src/homey/core/core-v0.11f.live-homey.js`.

De live Core doet gerichte reads van de bekende devices, maar voert **nog steeds één brede `Homey.logic.getVariables()` enumeratie per Core-run** uit. Dit is een bekende resterende Homey-load/throttling-optimalisatie en mag in documentatie niet worden voorgesteld alsof Core al volledig targeted/event-driven is.

Core voert geen fysieke device-writes uit. Fysieke aansturing blijft downstream via Power Intent / adapter / gate / actuator ownership.

## 3. Waarheidsbronnen en meetvaliditeit

Voor elektrische woningbalans en realtime flex-control is P1 leidend:

```text
P1 < 0 W → netto export
P1 > 0 W → netto import
```

P1 blijft autoritatief voor het realtime flexbudget. PV/huisreconstructie, Quooker-data en overige afgeleide belastingen ondersteunen state/diagnostiek maar mogen een geldige P1-gate niet vervangen.

Live Core v0.11f bevat Quooker Logic-data opnieuw in state/diagnostiek en `knownMeasuredLoadW`. Dit vervangt oudere ontwerpteksten waarin Quooker volledig uit Core werd verwijderd.

## 4. Rollen en fysieke ownership

| Verbruiker | Architectuurrol | Actuele ownership |
|---|---|---|
| Normaal huishouden | basislast | geen EMS-actuator |
| Quatt | comfort-baseload | observe-only |
| Boiler | flexload met comfortdoel | `Warm Water Actuator v0.9 TARGETED-READ LIVE` |
| Tesla | deadline/opportunity flexload | `EV Power v0.2.2 TARGETED-READ LIVE OWNERSHIP` |
| Quooker | gemeten/afgeleide load | geen actuele Core-actuatorownership |
| Victron-batterij | toekomstige batterijoptimizer | Victron DESS/ESS na installatie; Planner nu SHADOW |

Per fysieke actuator bestaat exact één automatische writer. Historische/replaced writers worden niet als huidige ownership gedocumenteerd.

## 5. Tesla en projected-grid headroom

Core v0.11f gebruikt voor Planner Tesla-admission:

```text
PLANNER_TESLA_MIN_POWER_W = 4140 W
projectedGridW = currentGridW + 4140 W
admission toegestaan wanneer projectedGridW <= 4000 W
```

Dit vervangt de eerdere onmogelijke vrije-importbudget-guard. MUST/latest-start catch-up behoudt prioriteit boven Planner opportunity/admission. Easee Equalizer blijft autonoom de lokale elektrische grens bewaken.

## 6. Contract- en prijsarchitectuur

Actuele productiebridge:

```text
Website FIXED/DYNAMIC
        │
        ▼
EMS Settings Sync v0.4 TARGETED 15-MIN LOW-LOAD
        │
        ▼
EMS_ContractType
        │
        ▼
Contract Price Adapter v0.10 FIXED+DYNAMIC LOW-LOAD
        │
        ├── FIXED   → FIXED_CONFIG_TARGETED / STATIC
        └── DYNAMIC → PBTH prijscontext
        │
        ▼
EM2_Contract_Type + EM2_ContractPrice_Context
        │
        ▼
Core / Planner
```

Bij FIXED wordt PBTH niet aangeroepen. Core consumeert `EM2_ContractPrice_Context`, `EM2_Contract_Type` en `TEMP_PBTH_JSON_BUFFER`; `EMS_ContractType` wordt niet rechtstreeks door Core gelezen. Legacy `M7_Price_*`/M7-contextsignalen bestaan nog als fallback/legacy input en zijn daarom nog een consolidatiepunt.

De geplande PBTH `<12h` event-refresh is een afzonderlijke DYNAMIC-only verbetering en is pas actuele architectuur nadat die is geïmplementeerd en gereconcilieerd.

## 7. Warm water en bronkeuze

De websitebronselector is productie-actief:

```text
Website BOILER/CV
      │
PIN → Worker → GitHub command
      │
      ▼
EMS Settings Sync v0.4
      │
      ├── EMS_HotWaterSource
      └── WW_Boilermodus
             │
             ▼
         Core v0.11f
             │
             ▼
Warm Water Actuator v0.9 LIVE
```

`WW_Boilermodus` is een directe, safety-critical Core-input. Een FIXED↔DYNAMIC contractwijziging mag deze variabele niet wijzigen. De gecontroleerde DYNAMIC→FIXED acceptatie op 30 augustus 2026 bevestigde deze scheiding.

Core behoudt de WW goal/thermostaatverificatie: verwarming moet eerst bevestigd zijn; een natuurlijke thermostaatstop wordt pas na de bevestigingsperiode als goal/on-temperature verwerkt. De fysieke actuatorroute blijft downstream van die Core-beslissing.

## 8. EMS Settings Sync

Actuele configuratieflow:

```text
EM v2 | 05 Config | EMS Settings Sync v0.4 TARGETED 15-MIN LOW-LOAD
```

De flow gebruikt stabiele Logic-ID's en targeted reads, geen brede Logic- of device-enumeratie. De normale no-op route schrijft niets wanneer requestId en gewenste toestand al overeenkomen.

Ondersteunde instellingen:

```text
hotWaterSource = BOILER | CV
contractType   = FIXED | DYNAMIC
```

De configuratieroute schrijft geen fysieke actuator.

## 9. 24h Energy Planner

Actuele planner:

```text
EM v2 | 45 Planner | 24h Energy Plan v0.4.9 SHADOW LOW-LOAD
```

De Planner is actief als SHADOW-planningslaag. `SHADOW` betekent hier niet obsolete: hij levert actuele plan/intents, maar verricht geen fysieke device-writes. Core blijft realtime safety-arbiter voor WW en Tesla.

Vereenvoudigde actuele keten:

```text
State + contract/prijs + Tesla/WW doelen + PV-context
                         │
                         ▼
              Planner v0.4.9 SHADOW
                         │
                  plan / slot intents
                         │
                         ▼
                   Core v0.11f
                         │
                realtime safety/gates
                         │
                         ▼
                 downstream writers
```

## 10. Actuele EV- en WW-lagen

EV:

```text
Core / policy
   ↓
P1 Power Intent v0.2.4
   ↓
EV adapter/gate-validatie
   ↓
EV Power v0.2.2 LIVE OWNERSHIP
   ↓
Easee
```

WW:

```text
Core / WW intent
   ↓
WW Power Adapter v0.2 SHADOW
   ↓
WW gates/validatie
   ↓
Warm Water Actuator v0.9 LIVE
   ↓
Boiler
```

De oudere WW actuator v0.6 en de vervangen Tesla v2.7.15-flow zijn geen actuele physical-write owners.

## 11. Aggregator en fan-out

`Core Snapshot Aggregator v0.2 SHADOW NO-QUOOKER` is een actieve shadow-component en heeft eerder parity rev107 met nul mismatches behaald. De naam `NO-QUOOKER` beschrijft het Aggregator-inputcontract; zij betekent niet dat de live Core v0.11f zelf geen Quooker-data bevat.

Fan-out-optimalisatie blijft een architectuurdoel: semantisch ongewijzigde state mag niet uitsluitend door timestamps/heartbeatmetadata downstream change-events veroorzaken.

## 12. Publicatie en observability

Actuele publicatielagen zijn onder andere:

- `Publisher v1.0.12 SCHEDULED LOW-LOAD`;
- `Planner Shadow v0.4 event-driven LOW-LOAD`;
- freshness watchdog v0.3.3;
- aparte historie/evidence/publicatielagen zoals geregistreerd in de runtime-baseline.

Website/publicatie is observability/configuratie en mag geen alternatieve fysieke actuatorroute creëren.

## 13. Victron-doelarchitectuur

Victron Dynamic ESS (DESS) is de beoogde primaire batterijoptimizer. Homey/Planner orkestreert huishoudelijke flexibiliteit en mag geen concurrerende realtime batterijoptimizer worden.

Zolang Victron niet fysiek geïntegreerd is, blijft batterijgedrag in de Planner simulatie/SHADOW. De bestaande PV-omvormers blijven AC-gekoppeld.

## 14. Veiligheidshiërarchie

```text
Installatieveiligheid / 3×25 A
          ↓
Lokale apparaatbeveiligingen
          ↓
Easee Equalizer
          ↓
Victron DESS / ESS (na installatie)
          ↓
Energy Core v2 + Homey-orchestratie
          ↓
Gevalideerde huishoudelijke actuator-writers
```

## 15. Documentatie- en synchronisatieregel

Procesflowdiagrammen beschrijven altijd de **actuele gecodeerde stand**. Voor current-state documentatie geldt de authority order uit `docs/architecture/current-runtime-source-policy.md`.

`start_flow()` bewijst alleen dat een flow is gestart; het bewijst niet dat downstream verwerking is voltooid. E2E-validatie moet daarom eindigen op aantoonbare runtime/readback-evidence.

Historische candidate-, patch-, smoke-, rollback-, TEMP-, DONE- en ONE-SHOT-bestanden mogen voor audit/rationale blijven bestaan, maar mogen niet als actuele architectuur worden samengevoegd.

## 16. Bekende open optimalisaties

De huidige gereconcilieerde baseline heeft nog expliciete verbeterpunten:

1. Core brede `Homey.logic.getVariables()` enumeratie vervangen/verminderen zonder functionele regressie;
2. PBTH DYNAMIC `<12h` event-driven prijsrefresh afronden;
3. resterende legacy M7 prijs/context-afhankelijkheden consolideren;
4. Round 2B legacy/rollback/validation-flow cleanup dependency-by-dependency uitvoeren;
5. verdere WW/Tesla runtime-validatie uitvoeren waar de acceptatiecriteria dat vereisen;
6. Victron-integratie pas promoveren van SHADOW wanneer hardware/commissioning gereed en gevalideerd is.
