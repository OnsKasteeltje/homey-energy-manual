# Energy Core v2 — greenfield architectuur

## Status

**Implementatiefase:** parallelle opbouw / read-only SHADOW.  
**Legacy blijft leidend:** nee: na de handmatige opschoning is de eerder opgebouwde energie-controlketen op 17 augustus 2026 grotendeels gedeactiveerd.  
**Doel:** Homey als lichte edge-orchestrator; website en historie volledig los van de kritische regelroute.

> Baselinecontrole 17 augustus 2026: `Energy Manager State Collector v1.0`, `Energy Manager Allocator - Shadow v0.2.4`, `Tesla laden v2.6`, `Warm water optimalisatie - PV boiler + CV advies v1.3`, `Live energie publicatie v1.2` en `Tesla runtime publicatie v1.3` zijn disabled en niet broken. De oude standaardflows `Boiler aan`, `Boiler uit`, `Boiler opwarmen`, `Lader uit`, `Charger disabled due to insufficient export`, `Handmatig laden starten (10A)`, `Handmatig laden stoppen` en `Start laden Tesla 16A` zijn eveneens disabled. `Enable charger` is nog enabled en wordt voorlopig expliciet als programmatic/manual-fallback writer behandeld. Er is tijdens de v2-opbouw geen fysieke aansturing geactiveerd of gewijzigd.

## Harde architectuurregels

1. Homey leest apparaten en voert lokale intenties uit; Homey is geen website-backend of historische database.
2. Event-driven waar mogelijk; polling alleen voor forecast, deadlines, heartbeat en bronnen zonder bruikbare events.
3. Iedere fysieke meetwaarde wordt één keer genormaliseerd in de centrale Energy State en daarna hergebruikt.
4. Kleine fluctuaties worden door deadbands/hysterese onderdrukt voordat de decision-laag opnieuw rekent.
5. Per fysieke actuator bestaat exact één automatische writer.
6. Websitebezoek veroorzaakt nul Homey-calls: de site leest uitsluitend gepubliceerde snapshots.
7. Publicatie en historie zijn nooit onderdeel van de kritische control-route.
8. Shadow vergelijkt productie- en kandidaatbeslissingen op dezelfde state; geen duplicaatnetwerk van productieflows.
9. Victron/Easee verzorgen snelle lokale vermogens- en veiligheidsregeling; Homey regelt intentie op seconden/minuten-niveau.
10. Ontbrekende data blijft `null`/`UNKNOWN`; v2 verzint geen waarden.

## Doelarchitectuur

```text
Devices / meters / Victron / Easee
               │ events / beperkte polling
               ▼
        INPUT ADAPTERS
               │
               ▼
        ENERGY STATE v2
               │
       ┌───────┴────────┐
       ▼                ▼
 DECISION CORE       PUBLISHER
       │                │
       ▼                ▼
 CONTROL ADAPTERS   energy-state-v2.json
       │                │
 Tesla / Boiler /       ├─ website
 later Victron          └─ externe historie/analyse
```

## Homey-mappen v2

```text
Energy Core v2
├── 00 Input
├── 10 State
├── 20 Decision
├── 30 Control
├── 80 Shadow
├── 90 Publish
└── 99 Maintenance
```

Alle v2-objecten gebruiken een eigen namespace. Voor Logic/context: `EM2_*`.

## Implementatiestatus 17 augustus 2026

De eerste echte greenfield-kern is actief, maar uitsluitend read-only/shadow:

| Flow | Status | Homey-load | Fysieke writes |
|---|---|---|---|
| `Energy Core v2 - 10 State - Collector v0.2` | enabled | iedere 5 min één gedeelde `getDevices` + `getVariables`; Logic-write alleen bij materiaalwijziging of 30-min heartbeat | geen |
| `Energy Core v2 - 20 Decision + 80 Shadow v0.1` | enabled | iedere 5 min alleen `getVariables`; geen device-read | geen |

De State Collector schrijft `EM2_State` en zet `EM2_Publish_Due` alleen wanneer publicatie nodig is. Start-deadbands zijn 100 W voor vermogenswaarden, 0,5 A voor fasecurrenten en 0,02 kWh voor de Easee-meter; status- en deadlinewijzigingen zijn exact. De Decision/Shadow-laag leest uitsluitend `EM2_State`, classificeert `MUST / SHOULD / MAY`, schrijft `EM2_Decision` en `EM2_Shadow` en gebruikt `AGREE / DIFFER / NOT_COMPARABLE` alleen als observatie-uitkomst.

De eerste versie blijft bewust op één 5-minuten centrale snapshot. De Homey-kaarten bevestigen dat native change-events beschikbaar zijn voor P1, PV, Easee, Equalizer, boiler en apparaten. Nadat deze centrale v2-keten stabiel is gevalideerd kan de Input-laag stapsgewijs naar event-adapters worden omgezet, zonder de Decision/Shadow-contracten te wijzigen.

**Nog niet geïmplementeerd:** `30 Control` en `90 Publish`. Er bestaat dus nog geen v2-route die Tesla, boiler of Victron fysiek aanstuurt en `energy-state-v2.json` wordt nog niet vanuit deze nieuwe state gepubliceerd.

## Nieuwe Legacy-v1-baseline na handmatige deactivatie

| Flow | Classificatie | Status 17-08-2026 | Opmerking |
|---|---|---|---|
| `Energy Manager State Collector v1.0` | Input/State | disabled | read-only; 1× `getDevices` + 1× `getVariables` per 2 min wanneer actief |
| `Energy Manager Allocator - Shadow v0.2.4` | Decision/Shadow | disabled | leest alleen `EM_Runtime_State`; geen device writes |
| `Tesla laden v2.6` | productie/writer | disabled | automatische Easee-writer; directe devices-read + command-fetch per 2 min wanneer actief |
| `Warm water optimalisatie - PV boiler + CV advies v1.3` | productie/writer | disabled | boilerwriter; directe devices-read per 5 min wanneer actief |
| `Live energie publicatie v1.2` | publisher | disabled | leest centrale state; GitHub-publicatie per 5 min wanneer actief |
| `Tesla runtime publicatie v1.3` | publisher | disabled | deed eigen `getDevices` + GitHub-publicatie per 2 min wanneer actief |
| `Boiler aan / Boiler uit / Boiler opwarmen` | legacy boilerwriters | disabled | geen automatische legacy-boilerroute actief via deze flows |
| `Lader uit` | legacy EV-writer | disabled | geen vaste legacy-stoproute actief |
| `Charger disabled due to insufficient export` | legacy EV-writer | disabled | exportgestuurde legacy-route uit |
| `Handmatig laden starten/stoppen` en `Start laden Tesla 16A` | manual legacy writers | disabled | oude handmatige routes uit |
| `Enable charger` | manual/fallback writer | **enabled** | programmatic trigger; kan Easee fysiek enable-en en blijft bewust ongemoeid tot Control-cutover |

`Enable charger` telt daarom als expliciete uitzondering op de greenfield-isolatie. Vóór Tesla naar `HYBRID` of `ACTIVE` gaat moet deze route opnieuw worden beoordeeld, zodat er exact één automatische writer-eigenaar blijft en een eventuele handmatige/fallbackfunctie bewust gescheiden wordt.

## Centrale Energy State

De contractbron is `docs/data/energy-state-v2.schema.json`. De publisher levert uiteindelijk één actuele snapshot als `docs/data/energy-state-v2.json`.

De actieve Homey-state heet `EM2_State` en bevat momenteel:

- `grid`: netto vermogen, import/export en L1/L2/L3;
- `pv`: totaal en productie per drie omvormers;
- `tesla`: werkelijk vermogen, gevraagde stroom, laadstatus en Easee-meter;
- `equalizer`: totaal en fasecurrenten;
- `hotWater`: boilervermogen, aan/uit en bestaande warmwatermodus;
- `appliances`: wasmachine/droger status-only;
- `goals`: Tesla deadline, latest-start, resterende kWh en status;
- `context`: bestaande M7 prijs-/PV-context;
- metadata: schema, sample-, change-, publish-timestamp en revision.

Batterij/Victron wordt toegevoegd zodra de read-only Victronbron beschikbaar is. Ontbrekende data blijft expliciet onbekend.

## Event- en deadbandbeleid

Een ruwe capability-wijziging hoeft niet automatisch de hele Energy Manager te laten rekenen. Input adapters normaliseren eerst en markeren state alleen dirty bij relevante verandering.

Startwaarden voor tuning:

| Signaal | Nieuwe evaluatie bij |
|---|---:|
| Grid netto vermogen | ≥ 100 W wijziging of grensovergang |
| PV totaal | ≥ 100 W wijziging of grensovergang |
| Tesla werkelijk vermogen | ≥ 100 W of laadstatuswijziging |
| Boiler vermogen | ≥ 100 W of aan/uit-wijziging |
| Equalizer/fasecurrent | ≥ 100 W / 0,5 A |
| Easee energiemeter | ≥ 0,02 kWh |
| SOC later | ≥ 1 procentpunt |
| Deadline / MUST-status | iedere relevante statewijziging en periodieke deadline-tick |

Grensovergangen krijgen in de uiteindelijke event-adapters altijd voorrang boven de numerieke deadband.

## Dirty-state publisher

De websitepublisher wordt onafhankelijk van de control-route:

```text
relevante statewijziging / heartbeat
       ↓
EM2_Publish_Due = true
       ↓
90 Publish (nog te bouwen)
       ↓
energy-state-v2.json
       ↓
EM2_Publish_Due = false
```

De State Collector forceert daarnaast iedere 30 minuten een heartbeat-write, ook zonder materiële wijziging. Hierdoor kan de toekomstige publisher onderscheid maken tussen **geen relevante verandering** en **Homey/publisher niet meer gezond**.

## Websitecontract

De website krijgt geen kennis van individuele Homey-flows als operationele waarheid. Zij toont functionele state, bijvoorbeeld:

- `Energy Manager: SURPLUS_OPTIMIZATION`;
- `Tesla: beschikbaar voor opportunity charging`;
- `Boiler: dagdoel nog niet gehaald`;
- `Grid: 2,8 kW export`;
- `Laatste geldige state` en `laatste heartbeat`.

Tijdens de migratie mag de website v2 prefereren en alleen wanneer `energy-state-v2.json` ontbreekt terugvallen op de legacy snapshots. Zodra v2 stabiel is, wordt die fallback verwijderd.

## Control modes en cutover

| Mode | Betekenis |
|---|---|
| `LEGACY` | legacy productieflows sturen; v2 observeert |
| `SHADOW` | v2 state + decision actief, geen v2 device-writes |
| `HYBRID` | alleen expliciet gemigreerde actuators volgen v2 |
| `ACTIVE` | v2 is leidend voor alle gemigreerde flexloads |

**Huidige v2-mode: `SHADOW`.**

### Gecontroleerde cutover

1. Legacy-baseline vastleggen en bestaande writers expliciet classificeren. **Grotendeels gerealiseerd.**
2. V2 Input + State read-only activeren. **Gerealiseerd met State Collector v0.2.**
3. V2 Decision in shadow valideren. **Gestart met Decision + Shadow v0.1.**
4. V2 publisher en websitecontract activeren. **Nog te doen.**
5. Boiler-controladapter migreren en valideren. **Nog niet toegestaan.**
6. Tesla-controladapter migreren en Equalizer als onafhankelijke veiligheidslaag behouden. **Nog niet toegestaan.**
7. Wanneer alle productieactuators v2-eigendom hebben: resterende oude orkestratie-/shadow-/statuspublisherflows gecontroleerd deactiveren.
8. Oude flows minimaal één observatieperiode bewaren als rollback; niet direct verwijderen.

Veiligheids-, watchdog- of hardwarebeschermingsfuncties worden niet collectief uitgezet zonder afzonderlijke classificatie.

## Load-budget

Nieuwe v2-functionaliteit wordt alleen geaccepteerd wanneer zij binnen dit uitgangspunt past:

- geen websitepolling naar Homey;
- geen parallelle scripts die dezelfde capabilities uitlezen;
- geen permanente high-frequency polling voor optimalisatie;
- publishers maximaal op een lage vaste cadans en dirty-state;
- shadow gebruikt dezelfde centrale state en leest apparaten niet opnieuw;
- analyse/historie vindt buiten de kritische Homey-route plaats.

Vergeleken met de gedeactiveerde legacy-kern daalt de actieve centrale device-scan van iedere 2 minuten naar iedere 5 minuten. De Decision/Shadow-laag voegt daarbij geen device-read toe. Dit is een eerste structurele reductie; event-driven Input is de volgende optimalisatiefase.

## Rollback

De huidige read-only v2-kern kan zonder effect op fysieke apparatuur worden teruggedraaid door beide v2-flows uit te schakelen. Voor latere control geldt:

```text
v2 control writer UIT
legacy productieflow AAN
EM2_Control_Mode → SHADOW of LEGACY
```

Oude flows worden pas verwijderd nadat de nieuwe route langere tijd stabiel is gebleken.