# Energie Manager PV

**Modus:** Shadow / read-only  
**Homey-status:** 🟢 Actief  
**Actieve flow:** `Energie Manager PV - Shadow Mode v1.6.5`  
**Voorgaande flow:** `Energie Manager PV - Shadow Mode v1.6.4` — 🔴 Inactief

De actuele v1.6.5-flow is in Homey ingeschakeld. De flow werkt volledig in shadow/read-only-modus en stuurt geen Tesla, laadpaal of boiler aan. Hij observeert en berekent de gewenste energiesturing, houdt de boilerstatus en boilercycli bij, observeert de Easee/Equalizer-context en publiceert meetdata naar GitHub.

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

### Observer actief in v1.6.5

v1.6.5 voegt deze observatie daadwerkelijk toe zonder de laadpaal aan te sturen. Iedere run registreert aanvullend:

- totaal P1-vermogen;
- **P1 L1, L2 en L3 afzonderlijk**;
- Easee `target_charger_current`;
- werkelijk Tesla-laadvermogen;
- een uit werkelijk vermogen geschatte equivalente 3-fase laadstroom;
- verhouding tussen geleverd en gevraagd laadvermogen;
- afgeleide `equalizerState`.

De observer gebruikt voorlopig bewust conservatieve statussen:

| Status | Betekenis |
|---|---|
| `NOT_APPLICABLE` | geen bruikbare actieve laadvergelijking |
| `NOT_LIMITED` | Tesla laadt werkelijk en geleverd vermogen past voldoende bij de Easee-targetwaarde |
| `LIMITED` | Tesla laadt werkelijk, ≥6 A target is zichtbaar en minder dan 82% van het daarbij horende 3-fase vermogen wordt geleverd |
| `PAUSED_OR_BLOCKED` | ≥6 A target zichtbaar, maar de laadstatus is gepauzeerd; dit wordt **niet automatisch** aan de Equalizer toegeschreven |

De eerste v1.6.5-run is technisch geslaagd. Daarbij werden onder andere **L1/L2/L3**, Easee-target en werkelijk Tesla-vermogen gepubliceerd. De Tesla stond op dat moment `plugged_in_paused`, zodat terecht `PAUSED_OR_BLOCKED` is geregistreerd. Een echte `LIMITED`-situatie moet nog worden gevalideerd tijdens een laadsessie waarin de Equalizer aantoonbaar terugregelt.

### Gevraagd versus werkelijk Tesla-vermogen

De Energy Manager maakt hiermee expliciet onderscheid tussen:

- **gevraagde laadstroom / doelvermogen**;
- **werkelijke laadstroom / werkelijk vermogen** dat Easee na load balancing daadwerkelijk levert.

De nieuwe Flow-tags zijn:

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

Wanneer de Equalizer Tesla terugregelt, wordt het ogenschijnlijk vrijgekomen vermogen **niet automatisch direct aan de boiler toegewezen**. Eerst moet opnieuw worden beoordeeld:

- totaal P1-netvermogen;
- L1/L2/L3-fasebelasting;
- werkelijk Tesla-vermogen;
- boilerstatus en boilerconstraint;
- resterende veilige marge.

### Hysterese na Equalizer-ingreep

Voor de toekomstige actieve orchestratie geldt als ontwerpregel een korte stabilisatieperiode na onverwacht terugregelen of pauzeren van Tesla. Richtwaarde is **1–2 minuten** voordat vrijgekomen vermogen opnieuw aan een flexibele belasting wordt toegewezen.

De definitieve tijd wordt vóór activering in shadow mode gevalideerd.

## Boiler-observer en cyclusregistratie

De actuele v1.6.5-flow observeert de boiler zonder deze te schakelen. Een vermogen boven **1,5 kW** wordt als `VERWARMEN` beschouwd. Na minimaal 15 minuten bevestigd verwarmen en vervolgens minder dan **100 W gedurende 10 minuten** doorloopt de observer `AFKOELEN_WACHT` naar `OP_TEMPERATUUR`.

Boilercycli worden op basis van de 2-minutenmetingen bijgehouden en afgeronde cycli worden gepubliceerd naar:

`docs/data/boiler-cycles.json`

## 2-minuten sampler

De actieve v1.6.5-flow wordt iedere 2 minuten uitgevoerd. De persistente runtime-state staat in de eigen Homey Logic-string **`EM Shadow Runtime State v1.6.5`**.

## 15-minuten websitepublicatie

Dezelfde Advanced Flow heeft daarnaast een 15-minuten trigger. De actuele baseline wordt gepubliceerd naar:

`docs/data/shadow-baseline-v01.json`

De GitHub-JSON vormt een persistente websitehistorie van maximaal 720 gepubliceerde samples. Daarnaast worden afgeronde dagen compact bewaard in `docs/data/energy-daily-history.json`.

## Aangestuurde apparaten

**Geen.** v1.6.5 is volledig read-only/shadow. De flow observeert en registreert, maar voert geen fysieke schakelingen uit. De Easee Equalizer blijft autonoom de harde load-balancing-/veiligheidslaag.

## Versiebeheer

`Energie Manager PV - Shadow Mode v1.6.4` is uitgeschakeld. De actuele operationele shadow-versie is `Energie Manager PV - Shadow Mode v1.6.5`. Daarmee is binnen deze flowfamilie maximaal één versie actief.
