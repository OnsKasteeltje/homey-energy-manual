# Energy Manager — gefaseerde migratie naar centrale allocatie

## Doel

De bestaande Homey-regeling blijft tijdens de migratie operationeel. Nieuwe centrale beslislogica wordt eerst **read-only in shadow mode** toegevoegd en neemt pas na validatie per actuator de besturing over.

De migratie volgt vier principes:

1. **geen big-bang omschakeling**;
2. **één eigenaar per fysieke actuator**;
3. **strategie centraal, lokale veiligheid en uitvoering lokaal**;
4. **eerst meten en vergelijken, daarna pas sturen**.

## Baseline — 16 augustus 2026

Laatste bevestigde lokale Homey-sync:

| Functie | Productie/shadow | Bevestigde flow |
|---|---|---|
| Warm water | productie | `Warm water optimalisatie - PV boiler + CV advies v1.3` |
| Tesla | productie | `Tesla laden v2.6` |
| Energy Manager | shadow/read-only | `Energie Manager PV - Shadow Mode v1.6.6` |
| M7 Opportunity | shadow/read-only | `M7 - Opportunity Score - Shadow v1.3` |
| M7 prijs/PV | read-only | `M7 - Prijs en PV forecast context - read only` |
| Statuspublicatie | productie/systeem | `GitHub status sync - Homey lokaal v1.3` |

Deze set is de referentie voor fase 1–3. Geen van deze fysieke productieflows wordt voor de eerste migratiestappen gewijzigd.

## Control mode

De centrale migratie gebruikt één expliciete control mode:

| Waarde | Betekenis |
|---|---|
| `LEGACY` | alleen bestaande productieflows zijn leidend |
| `SHADOW` | centrale allocator rekent mee maar stuurt niets |
| `HYBRID` | alleen expliciet gemigreerde actuators volgen centrale opdrachten |
| `ACTIVE` | centrale Energy Manager is strategisch leidend voor alle gemigreerde flexloads |

Startwaarde: **`SHADOW`**.

## Stap 1 — centrale Energy State

De nieuwe Energy Manager leest alle relevante toestand via één logisch state-model. Dit model is read-only ten opzichte van fysieke apparaten.

Minimale velden:

- `gridPowerW` — netto P1; positief = import, negatief = export;
- `gridL1W`, `gridL2W`, `gridL3W` — fasecontext indien beschikbaar;
- `pvPowerW` — totale bekende PV-productie;
- `houseLoadW` — afgeleide of gemeten huisbelasting;
- `evConnected`;
- `evRequestedA`;
- `evActualPowerW`;
- `evDeadlineActive`;
- `evDeadlineAt`;
- `evRemainingKWh`;
- `boilerMode`;
- `boilerState`;
- `boilerPowerW`;
- `boilerGoalRemaining` — semantisch resterend dagdoel;
- `m7OpportunityScore`;
- `priceContext`;
- `pvForecastContext`;
- `equalizerState`;
- `batterySoc` — later Victron;
- `batteryPowerW` — later Victron;
- `victronEssState` — later Victron.

Ontbrekende data wordt expliciet `null`/`UNKNOWN`; de allocator mag daarvoor geen fictieve waarde aannemen.

## Stap 2 — centrale allocator vNext in shadow

De eerste allocator is **uitsluitend een beslismodel**. Hij schrijft niet naar Easee, boiler of Victron.

Output per cyclus:

- `controlMode`;
- `systemMode`;
- `teslaIntent`;
- `teslaTargetA`;
- `boilerIntent`;
- `batteryIntent`;
- `batteryTargetW`;
- `gridIntent`;
- `reasonCode`;
- `priorityClass`;
- `confidence`;
- `timestamp`.

Voorbeeld:

```json
{
  "controlMode": "SHADOW",
  "systemMode": "PV_SURPLUS",
  "teslaIntent": "WAIT",
  "teslaTargetA": 0,
  "boilerIntent": "HEAT",
  "batteryIntent": "UNAVAILABLE",
  "batteryTargetW": 0,
  "reasonCode": "BOILER_DAILY_GOAL_OPPORTUNITY",
  "priorityClass": "SHOULD"
}
```

## Beslisklassen

De allocator gebruikt niet langer één vaste volgorde Tesla → boiler. Iedere behoefte krijgt een beslisklasse:

### MUST

Een verplichting die vóór een grens moet worden uitgevoerd, bijvoorbeeld:

- Tesla-deadline bereikt de catch-upgrens;
- boiler moet het dagdoel nog halen en de uiterste verwarmingsgrens nadert.

### SHOULD

Uitvoeren wanneer het energetisch/economisch aantrekkelijk is, bijvoorbeeld:

- boiler vroegtijdig verwarmen met beschikbaar PV-overschot;
- Tesla vóór de deadline opportunistisch laden;
- later: accu laden bij gunstige prijs/PV.

### MAY

Pure flexibiliteit zonder harde verplichting, bijvoorbeeld:

- Tesla als exportbuffer wanneer geen deadline actief is.

Lokale veiligheidslagen kunnen iedere centrale opdracht beperken of blokkeren.

## Stap 3 — shadowvergelijking

Iedere centrale beslissing wordt naast de bestaande feitelijke regeling gelogd:

```text
werkelijke productieactie
        versus
centrale shadowbeslissing
```

Minimaal vergelijken:

- Tesla start/stop/gevraagde stroom;
- werkelijk Tesla-vermogen;
- boiler aan/uit en semantische boilerstatus;
- P1 voor en na een beslissing;
- Equalizer-ingreep;
- reden van afwijking;
- voorspelde versus werkelijke energieruimte.

Een verschil is een **analysepunt**, niet automatisch een fout.

## Migratievolgorde actuators

Na succesvolle shadowvalidatie:

1. boiler eerst naar `HYBRID`;
2. daarna Tesla;
3. Victron eerst read-only toevoegen;
4. Victron-strategie in shadow valideren;
5. pas daarna beperkte strategische ESS-aansturing.

De boiler is de eerste kandidaat omdat de actuator in essentie binair is en geen dynamische load-balancing zoals Easee kent.

## Single-writer-regel

Tijdens `HYBRID` geldt per actuator exact één automatische schrijver:

```text
Energy Manager intent
      ↓
actuator-flow
      ↓
fysiek device
```

Legacy beslislogica voor een gemigreerde actuator wordt pas uitgeschakeld wanneer de nieuwe actuatorflow is gevalideerd en rollback getest.

## Rollback

Rollback blijft altijd één flowversie terug:

```text
nieuwe actuatorversie UIT
oude productieversie AAN
controlMode terug naar SHADOW of LEGACY
```

Geen migratiestap mag een destructieve wijziging aan de vorige werkende flow vereisen.

## Victron-grens

Victron wordt later de snelle batterij-/netregelaar. Homey geeft alleen strategische intenties en probeert geen snelle vermogensregelkring te implementeren.

```text
Homey Energy Manager
      ↓ strategisch doel
Victron ESS
      ↓ snelle lokale regeling
MultiPlus / batterij / grid
```

Easee Equalizer blijft onafhankelijk de lokale EV-load-balancing en installatiebescherming uitvoeren.

## Status van deze migratie

- [x] productiebaseline vastgelegd vanuit lokale Homey-sync
- [x] centrale Energy State gedefinieerd
- [x] allocator-outputcontract gedefinieerd
- [x] control modes `LEGACY/SHADOW/HYBRID/ACTIVE` gedefinieerd
- [ ] Homey Logic-variabelen/state-object aanmaken
- [ ] nieuwe Energy Manager allocator-subversie in Homey aanmaken
- [ ] shadowbeslissingen publiceren
- [ ] vergelijking met productiegedrag starten
- [ ] boiler als eerste actuator migreren

De nog open Homey-stappen mogen pas worden uitgevoerd wanneer directe Homey-toegang beschikbaar is. Tot dat moment verandert de fysieke regeling niet.
