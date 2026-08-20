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
           1 centrale snapshot / 5 min
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
Prijs/PV-context · GitHub-publicatie · historie · website/app
```

De Energy Manager ligt niet in het fysieke stroompad. Hij meet, classificeert en verdeelt beschikbare flexibiliteit. Installatieveiligheid en lokale hardwarebeveiliging blijven altijd hoger in de hiërarchie.

De architectuurgelaagdheid is daarmee expliciet:

1. fysieke veiligheidslaag;
2. meet-/State-laag;
3. context-/normalisatielaag;
4. Decision-/orkestratielaag;
5. Control-/actuatorlaag;
6. Victron-regellaag voor batterij/net zodra geïntegreerd;
7. presentatie-/documentatielaag buiten de fysieke control-loop.

Een wijziging mag deze laaggrenzen niet ongemerkt doorbreken.

## 2. Single-reader meetlaag

De actuele Core draait op een cadans van vijf minuten. Per Core Tick geldt als harde ontwerpgrens:

```text
maximaal 1 × Homey.devices.getDevices()
maximaal 1 × Homey.logic.getVariables()
```

Daaruit wordt één revision-consistente snapshot opgebouwd. P1, PV, Tesla/Easee, boiler, Quatt en appliance-status worden vervolgens zoveel mogelijk **in-memory** verwerkt op dezelfde revision.

Downstream-logica mag niet opnieuw dezelfde devices gaan pollen wanneer de benodigde gegevens al in de Core-snapshot aanwezig zijn. Prijs- en PV-forecastcontext mag onafhankelijk worden vernieuwd, maar zonder daarvoor opnieuw de volledige Homey-devicecollectie uit te lezen.

## 3. Architectuur-invariant: Homey structureel ontlasten

**Homey zo licht mogelijk houden is een blijvende architectuurrichtlijn en geen tijdelijke performance-optimalisatie.** Nieuwe functionaliteit wordt standaard ontworpen volgens:

```text
één keer meten
      ↓
centrale snapshot delen
      ↓
in-memory/contextverwerking
      ↓
beslissen
      ↓
alleen noodzakelijke publicatie / actuatorwrite
```

Daaruit volgen de volgende bindende regels:

- **Geen dubbele device-scans.** Een nieuwe detector, classifier, publisher of beslisflow mag geen eigen volledige `getDevices()`-scan toevoegen wanneer de benodigde gegevens uit de bestaande Core-snapshot kunnen komen.
- **Geen dubbele logic-scans.** Hetzelfde geldt voor `getVariables()`; downstream consumers hergebruiken de bestaande snapshot/context.
- **Event-driven waar zinvol.** Voor snel veranderende signalen die niet op de vijfminutencadans kunnen wachten, heeft een gerichte event-trigger de voorkeur boven frequente volledige Homey-polling.
- **Core-snapshot als standaard fallback.** Wanneer event-driven niet nodig of niet betrouwbaar beschikbaar is, wordt de bestaande vijfminuten-Core-snapshot gebruikt in plaats van een tweede poller.
- **Geen UI-polling naar Homey.** Website/app leest uitsluitend gepubliceerde snapshots/data en veroorzaakt nooit Homey-devicecalls bij openen, refresh, navigeren of foreground/resume.
- **Publicatie is gethrottled en gedeeld.** Consumers lezen dezelfde gepubliceerde toestand; er worden geen zelfstandige publishers toegevoegd die daarvoor opnieuw devices uitlezen.
- **Historie is read-only ten opzichte van devices.** Historische logging gebruikt reeds beschikbare Core-/publicatiegegevens en creëert geen extra devicepolling of actuatorwrites.
- **Actuatorwrites blijven schaars en enkelvoudig.** Per fysieke actuator is uiteindelijk exact één automatische writer verantwoordelijk. Decision-/Shadow-/History-lagen schrijven niet rechtstreeks naar fysieke apparaten.
- **Geen polling als workaround zonder expliciete uitzondering.** Een tijdelijke snelle poller moet als tijdelijk worden gemarkeerd, voorzien zijn van een uitfaseringspad en mag niet stilzwijgend de doelarchitectuur worden.
- **Load-impact hoort bij iedere code-review.** Voor iedere nieuwe of gewijzigde flow moet expliciet worden gecontroleerd hoeveel extra `getDevices()`, `getVariables()`, API-calls, publishers en writes zij per uur toevoegt.

### 3.1 Toetsingsregel voor nieuwe functionaliteit

Voor iedere nieuwe detector of integratie geldt deze volgorde:

```text
1. Bestaat het signaal al in de Core-snapshot? → hergebruik snapshot
2. Zo nee: kan een gerichte event-trigger worden gebruikt? → event-driven
3. Zo nee: kan de 5-min Core Tick het signaal meenemen? → uitbreiden centrale read
4. Alleen als geen van bovenstaande kan → expliciete, gemotiveerde aanvullende poller
```

Een aanvullende poller is dus de **uitzondering**, niet de standaard.

### 3.2 Quooker als concreet voorbeeld

Quooker-detectie mag niet structureel gebaseerd blijven op korte-interval volledige Homey-device-snapshots. De doelroute is:

- event-driven op het relevante P1/fase-/device-signaal wanneer betrouwbaar beschikbaar; of
- classificatie op basis van de bestaande vijfminuten-Core-snapshot.

Hiermee wordt voorkomen dat een functioneel nuttige uitbreiding opnieuw Homey-throttling of rate-limitproblemen introduceert.

## 4. Waarheidsbronnen

Voor de elektrische woningbalans is **P1 leidend**:

```text
P1 < 0 W → netto export
P1 > 0 W → netto import
```

Apparaatmetingen verklaren vervolgens waar die belasting vandaan komt en welke delen flexibel zijn.

Belangrijk gevolg: een grootverbruiker die al in P1 zit, zoals Quatt, mag niet nogmaals van P1-export worden afgetrokken. Dat zou dubbel tellen.

De geldigheid van de directe P1/netmeting en de geldigheid van afgeleide huis/PV-balansen worden afzonderlijk beoordeeld. Stale of skewed PV-data maakt verse P1-data niet automatisch ongeldig.

## 5. Rollen van energieverbruikers

Niet iedere belasting heeft dezelfde regelvrijheid.

| Verbruiker | Architectuurrol | Flexibel? | Fysieke v2-Control |
|---|---|---:|---|
| Normaal huishouden | basislast | nee | n.v.t. |
| Quatt | `COMFORT_BASELOAD` | voorlopig nee | `OBSERVE_ONLY` |
| Boiler | flexload met comfortdoel | ja | Shadow tot expliciete cut-over |
| Tesla | flexload met optionele deadline | ja | afzonderlijke writer/migratie |
| Quooker | constraint/gebruikspatroon | beperkt | geen zelfstandige zware poller |
| Victron-batterij | toekomstige energie-/netbuffer | ja | later via Victron EMS |

Deze scheiding voorkomt dat comfortkritische ruimteverwarming op dezelfde manier wordt behandeld als een verplaatsbare boiler- of EV-load.

## 6. Quatt als comfortlast

De primaire elektrische Quatt-bron is `Quatt CIC.measure_power`. Quatt wordt uit dezelfde bestaande Core-snapshot gelezen en veroorzaakt dus geen extra Homey-poll.

Naast elektrisch vermogen kunnen diagnostische waarden worden meegenomen zoals thermisch vermogen, COP, working mode, thermostaatvraag en CV-request.

Quatt wordt gepubliceerd als:

```text
role         = COMFORT_BASELOAD
control_mode = OBSERVE_ONLY
controllable = false
```

Energy Core mag Quatt dus wel meewegen, maar niet fysiek begrenzen, uitschakelen of van setpoint veranderen zolang daar geen aparte veilige Control-policy voor is gevalideerd.

## 7. Centraal vermogensbudget

State publiceert één gedeeld `energy_budget` zodat Tesla, boiler en toekomstige batterijlogica niet ieder onafhankelijk dezelfde ruimte claimen.

Belangrijkste grootheden:

- totale geschatte woninglast;
- bekende flexlast;
- comfortlast Quatt;
- overige woninglast;
- grid safety reserve;
- Quatt-rampreserve;
- werkelijk vrij exportbudget voor flexloads;
- discretionair importbudget;
- toekomstige batterijsteun.

Kernformule:

```text
flex_export_budget
 = max(0,
       P1_export
       - 200 W gridreserve
       - Quatt-rampreserve)
```

Quatt-rampreserve:

```text
Quatt < 250 W        → 100 W reserve
Quatt ≥ 250 W        → max(350 W, 25% Quatt)
                        met maximum 750 W
```

De actuele bovengrens voor discretionaire flexstarts is 4.000 W totale actuele import. Dit budget is geen installatieveiligheidslimiet; fysieke installatiegrenzen en Easee-loadbalancing blijven hoger in de hiërarchie.

## 8. Decision-prioriteit

```text
1. Installatieveiligheid en lokale hardwarebeveiliging
2. Comfort-baseload: normaal huishouden + Quatt
3. Harde doelen/MUST
      ├─ Tesla deadline catch-up
      └─ warmwater catch-up
4. Economische flex-opportunities
      ├─ PV/flex-export
      ├─ negatieve prijs
      └─ goedkoop prijsvenster binnen importbudget
5. Rest naar net / later batterijbeleid
```

Een MUST-deadline mag een opportunistische load verdringen; gewone PV-/prijsoptimalisatie gebruikt alleen werkelijk beschikbare vrije ruimte.

## 9. Warm water en Tesla

Warm water gebruikt twee beslislagen:

```text
warmwatervraag → BOILER/CV-bronkeuze → timing → gevalideerde actuatorwriter
```

Bronkeuze en prijsadvies blijven read-only/Shadow totdat expliciet fysieke Control is vrijgegeven. Comfortdoel en deadline gaan vóór opportunistische optimalisatie.

Voor Tesla geldt dezelfde architectuurdiscipline: Decision gebruikt het gedeelde flexbudget; de Easee Equalizer blijft autonoom de feitelijke laadstroom begrenzen. Werkelijk laadvermogen is voor classificatie belangrijker dan alleen requested current.

## 10. Veiligheidshiërarchie

```text
Installatieveiligheid / 3×25 A
          ↓
Lokale apparaatbeveiligingen
          ↓
Easee Equalizer voor EV-loadbalancing
          ↓
Victron EMS voor batterij/net (later)
          ↓
Energy Core v2 flexorchestratie
          ↓
Gevalideerde actuator-writers
```

Homey probeert lokale beveiligingslagen nooit te overrulen.

## 11. Victron-doelarchitectuur

De geplande Victron-laag bestaat uit MultiPlus-II 48/5000, Cerbo GX MK2, VM-3P75CT en thuisbatterij. Victron wordt de primaire batterij-/netlaag; Homey blijft huishoudelijke orchestrator.

Zolang Victron niet geïntegreerd is geldt batterijsteun als 0 W. Na integratie kan Victron een toegestane batterijbijdrage aan hetzelfde gedeelde budget leveren. Dat verandert de rol van Quatt niet.

## 12. Publicatie, historie en website/app

Core Tick publiceert een gethrottlede, revision-consistente snapshot. De actuele runtimebaseline op 20 augustus 2026 is:

```text
publisher_version = EM2_CORE_PUBLISH_V0.10.4
schema_version    = 2.10
control_mode      = SHADOW
```

Bij de gevalideerde runtime waren `state_revision`, `decision_revision` en `shadow_revision` gelijk.

Website/app, Contract History en andere observatie-/documentatieconsumers staan buiten de kritische fysieke regelroute. Websitebezoek, app-refresh en History↔Live-navigatie mogen geen Homey-devicepolling veroorzaken.

### 12.1 Bekend operationeel punt — periodieke Homey-trigger

Op 20 augustus 2026 is incidenteel waargenomen dat een verwachte vijfminutenrun/publicatie niet aantoonbaar plaatsvond. Een gecontroleerde handmatige run van `EM v2 | 00 Core Tick | v0.10.4` publiceerde daarna direct succesvol een nieuwe, revision-consistente State/Decision/Shadow-snapshot. De Core-logica en GitHub-publicatieroute zijn daarmee functioneel aangetoond.

De bestaande `EM v2 | 05 Watchdog | Core Freshness v0.2.1` blijft als lichte safety net actief en leest in normale werking alleen `EM2_State`; hij voegt geen zelfstandige devicepolling toe. Omdat zowel Core als watchdog periodieke Homey-triggers gebruiken, wordt **geen aanvullende scheduler-/watchdogarchitectuur gebouwd zolang dit niet aantoonbaar een terugkerend operationeel probleem is**.

Status: **KNOWN / MONITOR — geen blocker voor de doelarchitectuur**. Heropenen alleen wanneer stale publicaties zich herhaaldelijk voordoen in normaal bedrijf. Dit voorkomt dat een incidentele schedulerafwijking leidt tot extra polling, parallelle schedulers of onnodige infrastructuurcomplexiteit.

## 13. Control- en writerdiscipline

Per fysieke actuator geldt als doelarchitectuur:

```text
State → Decision → Shadow/validatie → Control intent → exact één writer → actuator
```

Geen Contract History, uniforme prijscontext, WW Source Advice, website of andere observatielaag verricht rechtstreeks een fysieke actuatorwrite.

Iedere nieuwe fysieke Control-route wordt eerst in Shadow gevalideerd, krijgt een expliciete cut-over en moet rollbackbaar zijn.

## 14. Flowversionering

Voor iedere functionele flowfamilie geldt:

```text
inhoudelijke wijziging
      ↓
nieuwe hogere versie
      ↓
validatie
      ↓
nieuwe versie actief
oude versie uit / SUPERSEDED
```

Er mag maximaal één productieversie van dezelfde automatische flowfamilie actief zijn.

## 15. Architectuur-review bij iedere wijziging

Iedere relevante code-/flowwijziging wordt vóór vrijgave minimaal op deze punten getoetst:

- blijft de laagvolgorde meten → context → beslissen → Control → writer intact?
- wordt bestaande Core-data hergebruikt voordat nieuwe polling wordt toegevoegd?
- blijft het aantal volledige Homey-device- en logic-scans binnen de centrale Core-grens?
- voegt de wijziging nieuwe periodieke API-calls toe; zo ja, zijn die noodzakelijk en gethrottled?
- veroorzaakt website/app/history nog steeds 0 Homey-devicecalls?
- ontstaan er geen dubbele publishers of meerdere writers voor dezelfde actuator?
- blijft P1 de autoritatieve netmeting zonder dubbel tellen?
- blijven veiligheid, comfort en deadlines hoger dan economische optimalisatie?
- is nieuwe fysieke sturing eerst Shadow-gevalideerd?
- zijn tijdelijke workarounds expliciet tijdelijk en voorzien van een uitfaseringspad?
- zijn projectbaseline, runtime-status en gespecialiseerde documentatie tegelijk bijgewerkt?

## 16. Ontwerpprincipes

- meten vóór sturen;
- veiligheid vóór optimalisatie;
- comfortload is niet automatisch flexload;
- P1 is leidend en apparaatvermogen wordt niet dubbel geteld;
- één centrale read, meerdere in-memory consumers;
- **Homey-load minimaliseren is een harde architectuur-invariant**;
- event-driven boven snelle volledige polling;
- bestaande Core-snapshot boven aanvullende device-scan;
- website/app/historie veroorzaken geen Homey-devicepolling;
- deadlines boven opportunistische optimalisatie;
- lokale hardwarebeveiliging nooit overrulen;
- eerst Shadow, daarna gecontroleerde fysieke Control;
- exact één automatische writer per fysieke actuator;
- iedere inhoudelijke flowwijziging krijgt een nieuwe versie;
- documentatie en architectuur worden tegelijk met operationele wijzigingen bijgewerkt.

> Laatste architectuurupdate: **20 augustus 2026 — Energy Core v2 / runtimebaseline v0.10.4, schema 2.10.** Homey-load minimalisatie is expliciet geborgd als architectuur-invariant: één centrale read, gedeelde revision-consistente snapshot, in-memory consumers, event-driven waar nodig en geen UI-/history-devicepolling. Incidenteel missen van een periodieke run/publicatie staat als `KNOWN / MONITOR` geregistreerd en leidt zonder herhaald bewijs niet tot extra schedulercomplexiteit.