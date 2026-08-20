# Architectuuroverzicht

Deze pagina beschrijft de **actuele doelarchitectuur van Energy Core v2**. De oudere v1-opzet met losse State Collector, Allocator Shadow en meerdere zelfstandige publishers is niet meer leidend.

## 1. Hoofdstructuur

```text
FYSIEKE INSTALLATIE / VEILIGHEID
3×25 A · P1 · Easee Equalizer · lokale apparaatbeveiligingen
                    │
                    ▼
               METEN / STATE
P1 · PV · Easee · boiler · Quatt · overige relevante devices
                    │
           centrale Core-snapshot / 5 min
                    ▼
             ENERGY CORE v2
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
      State      Decision     Shadow
        │           │
        │      gedeeld energie-/flexbudget
        │           │
        └──────► Control intents
                    │
                    ▼
        afzonderlijk gevalideerde writers

Ondersteunend en buiten de fysieke control-loop:
Prijs/PV-context · lichte event-assisted detectors · GitHub-publicatie · historie · website/app
```

De Energy Manager ligt niet in het fysieke stroompad. Installatieveiligheid en lokale hardwarebeveiliging blijven altijd hoger in de hiërarchie.

## 2. Single-reader meetlaag

De Core draait op vijfminutencadans. Per Core Tick geldt als harde ontwerpgrens maximaal één volledige Homey-device-snapshot en één Logic-snapshot. Downstream-logica pollt dezelfde devices niet opnieuw wanneer de informatie al beschikbaar is.

Voor sneller veranderende signalen mag een **gerichte event-assisted detector** worden gebruikt wanneer de vijfminutencadans onvoldoende is. Zo'n detector mag geen nieuwe korte-interval `getDevices()`-scan introduceren.

## 3. Homey structureel ontlasten

Bindende volgorde voor nieuwe functionaliteit:

```text
1. Signaal al in Core-snapshot? → hergebruik
2. Gerichte event-trigger mogelijk? → event-driven/event-assisted
3. Vijfminuten-Core kan het meenemen? → centrale read uitbreiden
4. Alleen anders → expliciete aanvullende poller
```

Website/app veroorzaakt nul Homey-devicecalls. Publicatie en historie gebruiken reeds beschikbare toestand. Per fysieke actuator bestaat uiteindelijk exact één automatische writer.

### Quooker als gevalideerd voorbeeld

De Quooker-route is sinds 21 augustus 2026:

```text
Homey Cooker-switch = autoritatief OFF/ON
              │
              ├── OFF → OFF
              └── ON  → ON_IDLE
                         │
relevant P1/L3-event ────┴──► HEATING + power_w
```

Actieve detector: `EM v2 | 01 Quooker Detector | v0.3 SWITCH-AUTH + P1 HEATING`.

De detector gebruikt geen volledige `getDevices()`-snapshot. Alleen de Cooker wordt gericht gelezen; na een relevant P1-event kan aanvullend één gerichte P1-read plaatsvinden. Historisering gebruikt dezelfde reeds gedetecteerde toestand.

## 4. Waarheidsbronnen

Voor de elektrische woningbalans is P1 leidend:

```text
P1 < 0 W → netto export
P1 > 0 W → netto import
```

Apparaatmetingen verklaren de belasting. Een belasting die al in P1 zit wordt niet nogmaals van P1 afgetrokken.

Voor Quooker zijn de waarheidsbronnen bewust gescheiden:

- Homey switch → beschikbaar/aan-uit;
- P1/L3 → daadwerkelijk verwarmen en vermogen.

## 5. Rollen van energieverbruikers

| Verbruiker | Architectuurrol | Flexibel? | Fysieke v2-Control |
|---|---|---:|---|
| Normaal huishouden | basislast | nee | n.v.t. |
| Quatt | `COMFORT_BASELOAD` | voorlopig nee | `OBSERVE_ONLY` |
| Boiler | flexload met comfortdoel | ja | Shadow/gevalideerde writer |
| Tesla | flexload met optionele deadline | ja | afzonderlijke writer |
| Quooker | comfort/gebruikspatroon + gemeten load | beperkt | bestaande Quooker-flows; detector observe-only |
| Victron-batterij | toekomstige energie-/netbuffer | ja | later via Victron EMS |

## 6. Quatt als comfortlast

De primaire elektrische Quatt-bron is `Quatt CIC.measure_power`. Quatt wordt uit de Core-snapshot gelezen en veroorzaakt geen extra Homey-poll. Thermisch vermogen/COP zijn diagnostiek en tellen niet mee als elektrische last.

```text
role         = COMFORT_BASELOAD
control_mode = OBSERVE_ONLY
controllable = false
```

## 7. Centraal vermogensbudget

State publiceert één gedeeld `energy_budget` zodat Tesla, boiler en toekomstige batterijlogica niet onafhankelijk dezelfde ruimte claimen.

```text
flex_export_budget
 = max(0,
       P1_export
       - grid_safety_reserve
       - quatt_ramp_reserve)
```

De actuele gridreserve is 200 W. Quatt krijgt bij lage belasting een kleine reserve en bij actieve modulatie een begrensde rampreserve. Installatieveiligheid en Easee-loadbalancing blijven boven dit softwarebudget staan.

## 8. Decision-prioriteit

```text
1. Installatieveiligheid en lokale hardwarebeveiliging
2. Comfort-baseload
3. Harde doelen/MUST
4. Economische flex-opportunities
5. Rest naar net / later batterijbeleid
```

## 9. Warm water en Tesla

Warm water gebruikt bronkeuze, timing en een afzonderlijk gevalideerde actuatorroute. Comfortdoel/deadline gaan vóór opportunistische optimalisatie. Tesla gebruikt hetzelfde gedeelde flexbudget; Easee Equalizer blijft autonoom de feitelijke laadstroom begrenzen.

## 10. Veiligheidshiërarchie

```text
Installatieveiligheid / 3×25 A
          ↓
Lokale apparaatbeveiligingen
          ↓
Easee Equalizer
          ↓
Victron EMS (later)
          ↓
Energy Core v2
          ↓
Gevalideerde actuator-writers
```

## 11. Victron-doelarchitectuur

De geplande Victron-laag bestaat uit MultiPlus-II 48/5000, Cerbo GX MK2, VM-3P75CT en thuisbatterij. Victron wordt de primaire batterij-/netlaag; Homey blijft huishoudelijke orchestrator. Zolang Victron niet geïntegreerd is geldt batterijsteun als 0 W.

## 12. Publicatie, historie en website/app

Actuele runtimebaseline per 21 augustus 2026:

```text
Core              = EM v2 | 00 Core Tick | v0.10.5
publisher_version = EM2_CORE_PUBLISH_V0.10.5
schema_version    = 2.11
control_mode      = SHADOW
```

State, Decision en Shadow worden revision-consistent gepubliceerd. `loads.quooker` bevat switchstatus, heatingstatus, vermogen, freshness en transition history met bron `HOMEY_SWITCH_PLUS_P1_L3`.

Website/app leest uitsluitend de gepubliceerde toestand. De Live View toont zeven afzonderlijke consumenten: Tesla, Boiler, Ruimteverwarming, Wasmachine, Droger, Quooker en Overig. Alleen actief vermogen >20 W krijgt een actieve energiestroom.

### CI/publicatie-invariant

Een schemawijziging moet atomair worden verwerkt in publisher, adapter, tests, fixtures en repositoryvalidator. CI controleert daarnaast na bundling én na MkDocs-build dat de versiegebonden frontendbundle en het uiteindelijke Pages-artifact de actuele broncode/contractmarkers bevatten. Hiermee wordt voorkomen dat `main` nieuw is terwijl productie ongemerkt een oud artifact serveert.

## 13. Control- en writerdiscipline

```text
State → Decision → Shadow/validatie → Control intent → exact één writer → actuator
```

Observatie-, historie-, website- en detectorlagen verrichten geen fysieke writes tenzij zij expliciet als gevalideerde writer zijn ontworpen.

## 14. Flowversionering

Bij een inhoudelijke wijziging wordt een hogere flowversie gemaakt, gevalideerd en geactiveerd; de voorganger wordt uitgeschakeld/SUPERSEDED gehouden wanneer rollbackwaarde bestaat. Maximaal één productieversie per automatische flowfamilie is actief.

## 15. Architectuur-review

Iedere wijziging wordt getoetst op:

- extra Homey-load/API-calls;
- dubbele publishers/writers;
- correcte waarheidsbron;
- revision- en schema-consistentie;
- fail-safe gedrag bij stale/onbekende data;
- testbaarheid en rollback;
- synchroniteit tussen broncode, gegenereerde bundle en productie-artifact.

> Laatste update: **21 augustus 2026** — Core v0.10.5/schema 2.11, Quooker v0.3 switch-authoritative + P1 heating, Live View en CI/deploy-invarianten verwerkt.
