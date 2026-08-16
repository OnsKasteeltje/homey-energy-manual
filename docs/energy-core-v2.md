# Energy Core v2 — greenfield architectuur

## Status

**Implementatiefase:** parallelle opbouw / read-only.  
**Legacy blijft leidend:** nee: na de handmatige opschoning is de eerder opgebouwde energie-controlketen op 17 augustus 2026 grotendeels gedeactiveerd.  
**Doel:** Homey als lichte edge-orchestrator; website en historie volledig los van de kritische regelroute.

> Baselinecontrole 17 augustus 2026: Homey was weer stabiel genoeg voor een beperkte inventarisatie. `Energy Manager State Collector v1.0`, `Energy Manager Allocator - Shadow v0.2.4`, `Tesla laden v2.6`, `Warm water optimalisatie - PV boiler + CV advies v1.3`, `Live energie publicatie v1.2` en `Tesla runtime publicatie v1.3` zijn allemaal **disabled** en niet broken. Er is tijdens deze controle geen fysieke aansturing geactiveerd of gewijzigd.

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

## Nieuwe Legacy-v1-baseline na handmatige deactivatie

De flowlijst zelf bevat geen enabled-status; daarom zijn alleen de hieronder individueel gecontroleerde cruciale flows hard bevestigd.

| Flow | Classificatie | Status 17-08-2026 | Opmerking |
|---|---|---|---|
| `Energy Manager State Collector v1.0` | Input/State | disabled | read-only; 1× `getDevices` + 1× `getVariables` per 2 min wanneer actief |
| `Energy Manager Allocator - Shadow v0.2.4` | Decision/Shadow | disabled | leest alleen `EM_Runtime_State`; geen device writes |
| `Tesla laden v2.6` | productie/writer | disabled | automatische Easee-writer; directe devices-read + command-fetch per 2 min wanneer actief |
| `Warm water optimalisatie - PV boiler + CV advies v1.3` | productie/writer | disabled | boilerwriter; directe devices-read per 5 min wanneer actief |
| `Live energie publicatie v1.2` | publisher | disabled | leest centrale state; GitHub-publicatie per 5 min wanneer actief |
| `Tesla runtime publicatie v1.3` | publisher | disabled | read-only, maar deed eigen `getDevices` + GitHub-publicatie per 2 min wanneer actief |

Deze baseline laat zien dat de handmatige deactivatie de kern van de eerder opgebouwde regeling daadwerkelijk heeft stilgezet. Dit verlaagt de runtime-load, maar betekent ook dat Tesla-/boilerautomatisering en de centrale live-publicatie niet meer door deze flows worden uitgevoerd. Oude standaardflows met namen als `Boiler aan/uit`, `Lader uit`, `Enable charger`, handmatige laadflows en oudere energieflows bestaan nog; hun enabled-status is niet in bulk afgeleid en zij worden vóór een toekomstige control-cutover afzonderlijk als safety/manual/legacy-writer geclassificeerd.

## Centrale Energy State

De contractbron is `docs/data/energy-state-v2.schema.json`. De publisher levert uiteindelijk één actuele snapshot als `docs/data/energy-state-v2.json`.

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
relevante statewijziging → EM2_STATE_DIRTY = true

5-min publisher tick:
  dirty = false → geen volledige publicatie
  dirty = true  → snapshot publiceren, dirty wissen

30-min heartbeat:
  altijd meta.heartbeat verversen
```

Zo kan de website onderscheid maken tussen **geen relevante verandering** en **publisher/Homey niet meer gezond**.

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
2. V2 Input + State read-only activeren.
3. V2 Decision in shadow valideren.
4. V2 publisher en websitecontract activeren.
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

### Concrete lessen uit de gecontroleerde legacyflows

De oude centrale state + allocator is al een nuttige tussenstap: de allocator leest geen devices opnieuw. Voor v2 verbeteren we nog drie punten: de State Collector gaat van vaste 2-minuten volledige device-list-read naar events/deadbands plus een lage heartbeat; Tesla-control leest straks de centrale state in plaats van opnieuw alle devices op te vragen, behalve waar een expliciete veiligheids-read noodzakelijk is; en de Tesla-runtimepublisher wordt samengevoegd met de centrale dirty-statepublisher zodat geen aparte 2-minuten device-read + GitHub-write nodig is.

## Rollback

Rollback blijft expliciet en niet-destructief:

```text
v2 control writer UIT
legacy productieflow AAN
EM2_Control_Mode → SHADOW of LEGACY
```

Oude flows worden pas verwijderd nadat de nieuwe route langere tijd stabiel is gebleken.