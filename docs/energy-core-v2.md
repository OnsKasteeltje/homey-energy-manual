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

## Actuele v2 Homey-flows

- `EM v2 | 10 State | Collector v0.2` — actief, één centrale device/logic-read per 5 minuten, 100 W-deadbands en 30-minuten heartbeat; geen device writes en geen netwerk-I/O.
- `EM v2 | 20 Decision + 80 Shadow | v0.1` — actief; leest uitsluitend `EM2_State`, schrijft alleen `EM2_Decision`/`EM2_Shadow`; geen device reads, device writes of netwerk-I/O.
- `EM v2 | 90 Publish | State Publisher v0.1` — wordt als enige websitepublisher voor v2 gebruikt; leest uitsluitend `EM2_*` Logic-state en publiceert `docs/data/energy-state-v2.json` bij dirty state of een 30-minuten heartbeat. Deze laag staat buiten de control-route en heeft geen toegang tot actuators.

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

## Centrale Energy State

De interne Homey-state is `EM2_State`. Dit interne contract mag Homey-georiënteerd blijven. Het publieke websitecontract is bewust een aparte vertaling en wordt vastgelegd door `docs/data/energy-state-v2.schema.json`; de publisher levert `docs/data/energy-state-v2.json`.

Belangrijkste domeinen:

- `grid`: netto vermogen en fasen;
- `pv`: totaal en productie per omvormer;
- `battery`: SOC, vermogen en richting wanneer Victron beschikbaar is;
- `tesla`: aangesloten/laden/werkelijk vermogen/gevraagde stroom/deadlinebehoefte;
- `hot_water`: boilervermogen, warmtevraag en dagdoel;
- `loads`: alleen werkelijk gemeten of expliciet status-only apparaten;
- `manager`: control mode, state, beslissing, reden en actieve constraints;
- `meta`: timestamp, heartbeat, schema- en publisher-versie.

## Event- en deadbandbeleid

Een ruwe capability-wijziging hoeft niet automatisch de hele Energy Manager te laten rekenen. Input adapters normaliseren eerst en markeren state alleen dirty bij relevante verandering.

Startwaarden voor tuning:

| Signaal | Nieuwe evaluatie bij |
|---|---:|
| Grid netto vermogen | ≥ 100 W wijziging of grensovergang |
| PV totaal | ≥ 100 W wijziging of grensovergang |
| Tesla werkelijk vermogen | ≥ 100 W of laadstatuswijziging |
| Boiler vermogen | ≥ 100 W of aan/uit-wijziging |
| Batterijvermogen | ≥ 100 W of richtingwijziging |
| SOC | ≥ 1 procentpunt |
| Deadline / MUST-status | iedere relevante statewijziging en periodieke deadline-tick |

Grensovergangen krijgen altijd voorrang boven de numerieke deadband.

## Dirty-state publisher

De websitepublisher werkt onafhankelijk van de control-route:

```text
relevante statewijziging → EM2_Publish_Due = true

5-min publisher tick:
  publish_due = false + heartbeat < 30 min → geen GitHub-call
  publish_due = true → snapshot publiceren, vlag na succes wissen
  heartbeat ≥ 30 min → snapshot publiceren, ook zonder statewijziging
```

De publisher leest geen devices. Hij vertaalt `EM2_State`, `EM2_Decision` en `EM2_Shadow` naar één stabiel publiek `energy-state-v2.json`. Alleen na een succesvolle GitHub-write wordt `EM2_Publish_Due` gewist. Zo kan de website onderscheid maken tussen **geen relevante verandering** en **publisher/Homey niet meer gezond** zonder extra Homey-load.

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
| `LEGACY` | huidige productieflows sturen; v2 observeert |
| `SHADOW` | v2 state + decision actief, geen v2 device-writes |
| `HYBRID` | alleen expliciet gemigreerde actuators volgen v2 |
| `ACTIVE` | v2 is leidend voor alle gemigreerde flexloads |

### Gecontroleerde cutover

1. Legacy-baseline vastleggen en bestaande writers expliciet classificeren.
2. V2 Input + State read-only activeren. **Uitgevoerd.**
3. V2 Decision in shadow valideren. **Actief; 24-uurs observatievenster gestart.**
4. V2 publisher en websitecontract activeren. **In uitvoering op 17 augustus 2026.**
5. Boiler-controladapter migreren en valideren.
6. Tesla-controladapter migreren en Equalizer als onafhankelijke veiligheidslaag behouden.
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

## Rollback

Rollback blijft expliciet en niet-destructief:

```text
v2 control writer UIT
legacy productieflow AAN
EM2_Control_Mode → SHADOW of LEGACY
```

Oude flows worden pas verwijderd nadat de nieuwe route langere tijd stabiel is gebleken.
