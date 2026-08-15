# Energie Manager PV

**Modus:** Shadow / read-only  
**Homey-status:** 🟢 Actief  
**Actieve flow:** `Energie Manager PV - Shadow Mode v1.6.6`  
**Voorgaande flow:** `Energie Manager PV - Shadow Mode v1.6.5` — 🔴 Inactief

De actuele v1.6.6-flow is in Homey ingeschakeld. De flow werkt volledig in shadow/read-only-modus en stuurt geen Tesla, laadpaal, boiler, wasmachine of droger aan. Hij observeert en berekent de gewenste energiesturing, houdt de boilerstatus en boilercycli bij, observeert de Easee/Equalizer-context en publiceert meetdata naar GitHub.

## Berekening

```text
PV beschikbaar = max(0, -P1 + werkelijk Tesla-vermogen + werkelijk boilervermogen)
```

## Tesla-prioriteit

| Beschikbaar PV | Shadow-doel |
|---:|---:|
| < 4.140 W | 0 A |
| 4.140–4.829 W | 6 A |
| 4.830–5.519 W | 7 A |
| 5.520–6.209 W | 8 A |
| 6.210–6.899 W | 9 A |
| 6.900–7.589 W | 10 A |
| ≥ 7.590 W | 11 A |

Boiler wordt alleen toegestaan als na Tesla-reservering minimaal circa **2,1 kW** resteert.

## Easee Equalizer als harde veiligheidslaag

De **Easee Equalizer blijft altijd leidend voor lokale load balancing** van de laadpaal. De Energy Manager mag een begrenzing of laadpauze van de Equalizer nooit proberen te overrulen.

De regelhiërarchie is:

```text
Installatieveiligheid / 3×25 A
          ↓
Easee Equalizer load balancing
          ↓
Victron grid/batterijregeling (later)
          ↓
Homey Energy Manager / flex-orchestratie
          ↓
Tesla / boiler
```

Wanneer bijvoorbeeld tijdens Tesla-laden een oven of andere grote belasting wordt ingeschakeld, mag de Equalizer de Tesla-laadstroom zelfstandig verlagen of het laden pauzeren om overbelasting te voorkomen.

### Equalizer-observer

De observer registreert iedere run:

- totaal P1-vermogen;
- **P1 L1, L2 en L3 afzonderlijk**;
- Easee `target_charger_current`;
- werkelijk Tesla-laadvermogen;
- een uit werkelijk vermogen geschatte equivalente 3-fase laadstroom;
- verhouding tussen geleverd en gevraagd laadvermogen;
- afgeleide `equalizerState`.

De observer gebruikt bewust conservatieve statussen:

| Status | Betekenis |
|---|---|
| `NOT_APPLICABLE` | geen bruikbare actieve laadvergelijking |
| `NOT_LIMITED` | Tesla laadt werkelijk en geleverd vermogen past voldoende bij de Easee-targetwaarde |
| `LIMITED` | Tesla laadt werkelijk, ≥6 A target is zichtbaar en minder dan 82% van het daarbij horende 3-fase vermogen wordt geleverd |
| `PAUSED_OR_BLOCKED` | ≥6 A target zichtbaar, maar de laadstatus is gepauzeerd; dit wordt **niet automatisch** aan de Equalizer toegeschreven |

Een echte `LIMITED`-situatie moet nog worden gevalideerd tijdens een laadsessie waarin de Equalizer aantoonbaar terugregelt.

### Gevraagd versus werkelijk Tesla-vermogen

De Energy Manager maakt expliciet onderscheid tussen **gevraagde laadstroom / doelvermogen** en **werkelijke laadstroom / werkelijk vermogen** dat Easee na load balancing daadwerkelijk levert.

De Flow-tags zijn:

- `EM Shadow Tesla gevraagd A`;
- `EM Shadow Tesla werkelijk A est`;
- `EM Shadow Equalizer status`.

De baseline bevat daarnaast `p1L1W`, `p1L2W`, `p1L3W`, `teslaRequestedA`, `teslaRequestedW`, `teslaActualAEst`, `teslaDeliveryRatio` en `equalizerState`.

Voor toekomstige actieve orchestratie geldt:

```text
Homey vraagt laadstroom
        ↓
Easee / Equalizer bepaalt wat veilig geleverd kan worden
        ↓
Energy Manager accepteert werkelijk geleverd vermogen als actuele werkelijkheid
        ↓
geen directe poging om een veiligheidsbegrenzing te overrulen
```

### Geen foutieve herverdeling naar boiler

Wanneer de Equalizer Tesla terugregelt, wordt het ogenschijnlijk vrijgekomen vermogen **niet automatisch direct aan de boiler toegewezen**. Eerst worden totaal P1-netvermogen, L1/L2/L3-fasebelasting, werkelijk Tesla-vermogen, boilerstatus en resterende veilige marge opnieuw beoordeeld.

### Hysterese na Equalizer-ingreep

Voor de toekomstige actieve orchestratie geldt als ontwerpregel een korte stabilisatieperiode na onverwacht terugregelen of pauzeren van Tesla. Richtwaarde is **1–2 minuten** voordat vrijgekomen vermogen opnieuw aan een flexibele belasting wordt toegewezen. De definitieve tijd wordt vóór activering in shadow mode gevalideerd.

## Grootverbruikers-observatie in v1.6.6

v1.6.6 breidt de bestaande baseline-publicatie uit met de Homey-apparaatstatus van **Wasmachine** en **Droger**, zonder extra pollingflow en zonder fysieke aansturing.

De nieuwe velden zijn:

- `washerActive` — `true` uitsluitend wanneer Homey voor de wasmachine `measure_applianceState = RUNNING` rapporteert;
- `dryerActive` — `true` uitsluitend wanneer Homey voor de droger `measure_applianceState = RUNNING` rapporteert.

De Homey-apparaten leveren op dit moment geen individueel `measure_power`. Daarom wordt voor deze apparaten **geen wattage afgeleid of verzonnen**. De status wordt uitsluitend gebruikt om op de Live energiestroom-pagina zichtbaar te maken dat een bekende grootverbruiker actief is.

Bekende fasekoppeling:

- Wasmachine: **L2**;
- Droger: **L3**.

De vaatwasser blijft voorbereid in de visualisatie, maar krijgt pas een live status zodra een betrouwbare statusbron in de bestaande publicatie is opgenomen.

## Boiler-observer en cyclusregistratie

De actuele v1.6.6-flow observeert de boiler zonder deze te schakelen. Een vermogen boven **1,5 kW** wordt als `VERWARMEN` beschouwd. Na minimaal 15 minuten bevestigd verwarmen en vervolgens minder dan **100 W gedurende 10 minuten** doorloopt de observer `AFKOELEN_WACHT` naar `OP_TEMPERATUUR`.

Boilercycli worden op basis van de 2-minutenmetingen bijgehouden en afgeronde cycli worden gepubliceerd naar `docs/data/boiler-cycles.json`.

## 2-minuten sampler

De actieve v1.6.6-flow wordt iedere 2 minuten uitgevoerd. Om de lopende boiler-state-machine en historische cyclusregistratie niet te onderbreken, hergebruikt v1.6.6 bewust de bestaande Homey Logic-string **`EM Shadow Runtime State v1.6.5`**.

## 15-minuten websitepublicatie

Dezelfde Advanced Flow heeft daarnaast een 15-minuten trigger. De actuele baseline wordt gepubliceerd naar `docs/data/shadow-baseline-v01.json`.

De GitHub-JSON vormt een persistente websitehistorie van maximaal 720 gepubliceerde samples. Daarnaast worden afgeronde dagen compact bewaard in `docs/data/energy-daily-history.json`.

## Aangestuurde apparaten

**Geen.** v1.6.6 is volledig read-only/shadow. De flow observeert en registreert, maar voert geen fysieke schakelingen uit. De Easee Equalizer blijft autonoom de harde load-balancing-/veiligheidslaag.

## Versiebeheer

`Energie Manager PV - Shadow Mode v1.6.5` is uitgeschakeld. De actuele operationele shadow-versie is `Energie Manager PV - Shadow Mode v1.6.6`. Daarmee is binnen deze flowfamilie maximaal één versie actief.
