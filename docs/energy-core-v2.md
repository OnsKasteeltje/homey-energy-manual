# Energy Core v2 — greenfield architectuur

## Status

**Implementatiefase:** read-only SHADOW met eerste complete warmwater-controlketen.  
**Doel:** Homey als lichte edge-orchestrator; website en historie los van de fysieke regelroute.  
**Fysieke v2-writes:** geen.

Op 17 augustus 2026 is de v2-keten uitgebreid tot en met een warmwater-Control-adapter. De bestaande fysieke boilerregeling is niet door v2 overgenomen: v2 berekent uitsluitend wat hij *zou* doen en schrijft dat als Logic-state.

## Harde architectuurregels

1. Homey leest fysieke apparaten centraal en maximaal één keer per Energy Core-cyclus.
2. Downstream-lagen werken uitsluitend op genormaliseerde `EM2_*` state en lezen devices niet opnieuw.
3. Iedere fysieke meetwaarde wordt één keer genormaliseerd in de centrale Energy State.
4. Deadbands/hysterese onderdrukken kleine fluctuaties vóór downstream-evaluatie.
5. Per fysieke actuator bestaat uiteindelijk exact één automatische writer.
6. Websitebezoek veroorzaakt nul Homey-calls: de site leest uitsluitend gepubliceerde snapshots.
7. Historie en publicatie mogen geen extra device-scan veroorzaken.
8. Shadow en Control-intent werken op dezelfde State-revision.
9. Ontbrekende data blijft `null`/`UNKNOWN`; v2 verzint geen waarden.
10. Een v2-Control-adapter mag pas fysieke writes krijgen nadat de shadowvalidatie voldoende betrouwbaar is.

## Actuele keten

```text
Devices / meters / Easee
        │
        │ één centrale read per 5 min
        ▼
EM v2 | 10 State | Collector v0.5
        │
        ▼
EM2_State · revision N
        │
        ▼
EM v2 | 20 Decision + 80 Shadow | v0.4
        │
        ├── EM2_Decision · revision N
        ├── EM2_Shadow   · revision N
        │
        ▼
EM v2 | 15 State | Warm Water Observer v0.2
        │
        └── EM2_WW_State · revision N
        │
        ▼
EM v2 | 60 Control | Warm Water Actuator v0.3
        │
        ├── EM2_Control_WW · revision N
        └── GEEN fysieke write
        │
        ▼
EM v2 | 90 Publish | State Publisher v0.3
        │
        ▼
energy-state-v2.json → website

Parallel, zonder device-read:
EM v2 | 70 History | Day Series v0.1 → energy-day-v2.json
```

De oude `Collector v0.3/v0.4`, `Decision/Shadow v0.2/v0.3`, `Warm Water Observer v0.1` en `Warm Water Actuator v0.1/v0.2` zijn gedeactiveerde subversies. Er is per v2-module slechts één actuele subversie actief.

## Actieve v2 Homey-flows

| Laag | Actieve flow | Device-read | Device-write | Functie |
|---|---|---:|---:|---|
| State | `EM v2 | 10 State | Collector v0.5` | **1 centrale scan / 5 min** | nee | P1, PV, Tesla/Easee, Equalizer, boiler en appliance-status normaliseren |
| Decision + Shadow | `EM v2 | 20 Decision + 80 Shadow | v0.4` | nee | nee | energy state, intent, prioriteit en shadowvergelijking |
| Warmwater state | `EM v2 | 15 State | Warm Water Observer v0.2` | nee | nee | dagdoel, looptijd en thermostaatgedrag afleiden |
| Warmwater Control | `EM v2 | 60 Control | Warm Water Actuator v0.3` | nee | **nee** | `BOILER_ON`, `BOILER_OFF` of `HOLD` als shadow-intent |
| History | `EM v2 | 70 History | Day Series v0.1` | nee | nee | compacte dagreeks vanuit `EM2_State` |
| Publish | `EM v2 | 90 Publish | State Publisher v0.3` | nee | nee | revision-consistente GitHub-snapshot, gethrottled |

## Centrale Energy State

`EM2_State` is de enige fysieke energie-state voor downstream-regellogica. De Collector gebruikt deadbands van onder andere circa 100 W voor vermogen en een 30-minuten heartbeat. Een relevante verandering verhoogt de revision.

Decision/Shadow schrijft dezelfde `sourceRevision`. Warm Water Observer en Warm Water Control eisen eveneens een verse state en dezelfde revision. Publisher weigert te publiceren wanneer State, Decision en Shadow niet op dezelfde revision staan.

## Warmwater Observer v0.2

De warmwaterregeling gebruikt niet langer een continu draaiende legacy `WW_STATE_V13` als operationele bron. De v2 Observer leidt warmwatercontext af uit `EM2_State` en bewaart die in `EM2_WW_State`.

De Observer houdt bij:

- boiler-aan-tijd van vandaag;
- resterende 240-minuten fallbacktijd;
- of daadwerkelijk opwarmen is bevestigd;
- of `OP_TEMPERATUUR` is bereikt;
- of catch-up vóór 19:00 noodzakelijk wordt;
- kwaliteit van de huidige dagstate.

Voor thermostaatdetectie geldt voorlopig:

```text
boiler aan + vermogen > 1500 W gedurende 15 min
    → opwarmen bevestigd

daarna boiler nog aan + vermogen < 100 W gedurende 10 min
    → OP_TEMPERATUUR bereikt
```

De Observer wordt iedere State-cyclus gestart, maar doet geen device-read. Hij integreert elapsed time op zijn eigen run-tijd. Daardoor blijft de looptijd correct doorlopen wanneer `EM2_State` door een deadband niet opnieuw hoeft te worden geschreven.

Op de eerste v2-dag mag een geldige same-day `WW_STATE_V13` éénmalig als bootstrap worden gebruikt. Daarna is deze legacy-state geen runtime-afhankelijkheid meer. Als geen betrouwbare bootstrap beschikbaar is, is de dagstate expliciet `PARTIAL_FROM_START_TIME`; v2 verzint geen gemiste ochtendhistorie.

## Warmwater Control v0.3

De Control-adapter is bewust **PURE SHADOW**. Hij leest alleen:

- `EM2_State`;
- `EM2_Decision`;
- `EM2_WW_State`.

Hij schrijft uitsluitend `EM2_Control_WW`. Er bestaat in deze flow geen `Homey.devices`-write en geen boiler-actioncard.

### Huidig beleid

| Situatie | Shadow-intent | Prioriteit |
|---|---|---|
| State/Decision/WW-state niet vers of revision mismatch | geen actie / HOLD | MUST |
| elektrische boilermodus niet geselecteerd | `BOILER_OFF` indien nodig | MUST |
| `OP_TEMPERATUUR` bereikt | `BOILER_OFF` indien nodig | MUST |
| na 19:00 | geen nieuwe run / `BOILER_OFF` | MUST |
| catch-up noodzakelijk | `BOILER_ON` indien uit | MUST |
| 09:30–18:30 en ≥ 2100 W export | `BOILER_ON` | SHOULD |
| boiler ≥30 min aan en >500 W import | `BOILER_OFF` | SHOULD |
| anders | `HOLD` | MAY |

De 240 minuten zijn dus **fallback**, niet het primaire doel. Het primaire dagdoel blijft `OP_TEMPERATUUR`.

## Publisher v0.3

De websitepublisher leest geen devices. Bij wijzigingen wordt `EM2_Publish_Due=true`, maar GitHub wordt niet onbeperkt beschreven:

```text
relevante wijziging
    → dirty blijft pending
    → maximaal 1 GitHub-publicatie per 10 min

geen wijziging
    → heartbeat maximaal iedere 30 min
```

Een defer wist de pending dirty-status niet en veroorzaakt geen extra Logic-write. De praktijktest op 17 augustus 2026 bevestigde `publisher_version = EM2_PUBLISH_V0.3`, `publish_reason = DIRTY_THROTTLED` en `min_publish_interval_sec = 600`.

## Website en historie

Homepage, Live energiestroom en Energie Dagoverzicht gebruiken de v2-publicaties. Een websitebezoek veroorzaakt geen Homey-call.

- Live/Home: `energy-state-v2.json`;
- Dagoverzicht: `energy-day-v2.json`;
- refresh en health worden in de browser afgehandeld;
- huidige fysieke waarden en beslissingen blijven revision-consistent.

## Control modes

| Mode | Betekenis |
|---|---|
| `SHADOW` | huidige mode: v2 observeert en berekent control-intent, geen v2 device-writes |
| `HYBRID` | alleen expliciet gevalideerde actuators mogen door v2 worden gestuurd |
| `ACTIVE` | v2 is leidend voor alle gemigreerde flexloads |

De eerstvolgende promotie is **niet** automatisch HYBRID. Eerst moet Warm Water Control een volledige echte verwarmingscyclus correct volgen: start/opwarmen → thermostaat afslag → `OP_TEMPERATUUR` → passend stop-intent, inclusief PV/import- en catch-up-situaties.

## Load-budget

De huidige v2-keten voldoet aan het bedoelde loadmodel:

- één centrale `getDevices()` per 5 minuten;
- Decision/Shadow: alleen Logic;
- Warm Water Observer: alleen Logic, één kleine derived-state write per cyclus;
- Warm Water Control: alleen Logic;
- History: alleen bestaande `EM2_State`;
- Publisher: geen devices, GitHub-write maximaal iedere 10 minuten bij wijzigingen;
- website: nul Homey-calls.

## Rollback

De migratie blijft niet-destructief. Oude versies worden gedeactiveerd en voorlopig niet verwijderd. Omdat Warm Water v2 nog SHADOW is, is voor deze stap geen fysieke writer naar v2 overgezet.

> Laatste update: **17 augustus 2026** — Warm Water Observer v0.2 en Warm Water Actuator v0.3 geïntegreerd in de revision-consistente Energy Core v2-keten; Publisher v0.3-throttle in praktijk bevestigd.
