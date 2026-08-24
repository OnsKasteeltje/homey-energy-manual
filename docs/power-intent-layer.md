# Power Intent Layer v0.1

## Status

**Branch:** `main`  
**Fase:** architectuur / SHADOW  
**Fysieke actuatorwijzigingen:** geen  
**RC-impact:** geen; `rc-2026-08-24` blijft onaangetast

## Doel

De Power Intent Layer maakt de scheiding expliciet tussen **EMS-besluitvorming** en **apparaat-specifieke actuatie**.

De Energy Core beslist voortaan conceptueel in functionele vermogensintenties in watt. Alleen de actuator-adapter vertaalt die intentie naar apparaat-specifieke commando's, zoals Easee-ampères, een boilerrelais of een Victron/ESS-setpoint.

```text
State / Context
      ↓
Energy Core
      ↓
Policy / Arbiter
      ↓
Power Intent Layer
      ├── EV_target_W
      ├── WW_target_W
      └── Battery_target_W
      ↓
Actuator adapters
      ├── Easee adapter → A/fasen
      ├── Boiler adapter → ON/OFF
      └── Victron adapter → ESS/setpoint
      ↓
exact één writer per actuator
```

## Relatie met Homey native `target_power`

Homey ondersteunt native `target_power` en `target_power_mode`. Dit wordt gebruikt als referentiesemantiek en waar betrouwbaar mogelijk als native capability, conform guardrail G1 (native Homey vóór maatwerk).

Belangrijk: het gebruik van `target_power_mode=homey` betekent binnen dit project **niet** dat Homey's generieke Energy-logica eigenaar wordt van onze EMS-policy. Energy Core blijft de beleidsmatige arbiter voor deadlines, contracttype, comfort, PV-budget en prioriteiten.

De native capability is een actuator-/capability-interface, geen vervanging van de Energy Core.

## Canonieke tekenconventie

Voor de interne Power Intent Layer volgen we Homey's vermogensrichting:

```text
+W = verbruik / laden uit AC-zijde
 0 = idle / geen vermogensvraag
-W = teruglevering / ontladen naar AC-zijde
```

Voorbeelden:

```text
EV_target_W       = +6200   # Tesla laden
WW_target_W       = +1900   # boiler verwarmen
Battery_target_W  = -2500   # batterij ontladen naar AC/net/huis
Battery_target_W  = +2500   # batterij laden
```

Adapters mogen deze semantiek intern naar apparaat-specifieke tekenconventies vertalen, maar de Core verandert de betekenis niet per apparaat.

## Resource-intents

### Tesla / EV

Tesla/Easee is een variabele flexload. De Core publiceert een gewenst laadvermogen in watt.

De Easee-adapter vertaalt dit naar een technisch uitvoerbare laadinstelling en respecteert minimaal:

- beschikbare fasen;
- minimale en maximale laadstroom;
- EV-minimumvermogen/deadband;
- lokale Easee Equalizer-ingreep;
- bestaande deadline/MUST-prioriteit;
- rate-limit/write-throttling;
- single-writer en run-lease/idempotency.

Een target onder het technisch betrouwbare minimum wordt niet continu naar lage ampèrewaarden vertaald, maar valt via de deadband terug naar `0 W` tenzij een expliciete MUST/deadline-policy anders vereist.

### Warm water / boiler

De boiler is praktisch een binaire flexload. De Core kan hem toch uniform als vermogensintent modelleren:

```text
WW_target_W = 0      → OFF
WW_target_W ≈ 1900   → ON
```

De boiler-adapter vertaalt de functionele intentie naar de bestaande gevalideerde ON/OFF-writer. Er wordt geen fictieve vermogensmodulatie geïntroduceerd.

### Victron / batterij

Na fysieke integratie wordt de batterij de eerste bidirectionele resource:

```text
Battery_target_W > 0  → laden
Battery_target_W = 0  → idle
Battery_target_W < 0  → ontladen
```

De Victron-adapter vertaalt dit naar de gekozen ESS/Modbus-interface. Victron-lokale BMS/ESS/safety-regels blijven hoger in de veiligheidshiërarchie en mogen een target begrenzen of weigeren.

## Arbiter en budget

De bestaande centrale vermogensbudgettering blijft leidend. De Power Intent Layer vervangt `flex_export_budget_w` niet, maar maakt expliciet **hoe dat budget aan resources wordt toegewezen**.

Voorbeeld:

```text
flex_export_budget_w = 5000

EV_target_W = 3000
WW_target_W = 1900
Battery_target_W = 0
unallocated_W = 100
```

De som van discretionaire positieve intents mag nooit meer claimen dan het door de policy vrijgegeven budget, behalve voor expliciete MUST/deadline-loads waarvoor gecontroleerde import is toegestaan.

## Idempotency en write-discipline

De adapter schrijft alleen wanneer het **effectieve uitvoerbare target** relevant verandert.

Conceptueel:

```text
desired_intent_W
      ↓
clamp + device constraints + deadband
      ↓
effective_target
      ↓
vergelijk met last_applied_target
      ├── gelijk / binnen hysterese → NO-OP
      └── relevante wijziging → writer
```

De bestaande run lease, dedup en single-writer-invarianten blijven verplicht. De Power Intent Layer creëert geen tweede actuatorroute.

## Hysterese en stabiliteit

Resource-adapters krijgen expliciete stabiliteitsregels zodat snelle PV-variatie niet tot schrijf-pingpong leidt. Minimaal worden onderscheiden:

- technische deadband rond 0 W;
- minimaal uitvoerbaar vermogen;
- minimale relevante targetdelta;
- minimale stabiele duur voordat een nieuw discretionair target wordt toegepast;
- afzonderlijke regels voor MUST/deadline versus opportunity-control.

Concrete waarden worden per adapter in SHADOW gemeten en gevalideerd voordat fysieke cut-over plaatsvindt.

## State-contract v0.1

Voorgestelde canonieke intent-state:

```json
{
  "schema": "EM2_POWER_INTENT_V0.1",
  "sourceRevision": 0,
  "mode": "SHADOW",
  "targets": {
    "ev_w": 0,
    "ww_w": 0,
    "battery_w": 0
  },
  "reasons": {
    "ev": null,
    "ww": null,
    "battery": null
  },
  "budget": {
    "flex_export_budget_w": 0,
    "discretionary_import_budget_w": 0
  },
  "writeAllowed": false
}
```

Iedere intent verwijst naar dezelfde `sourceRevision` als de State/Decision waaruit hij is afgeleid.

## Migratiepad

### Fase P0 — architectuur

- interface en tekenconventie vastleggen;
- native Homey `target_power`/`target_power_mode` toetsen;
- geen actuatorwrites wijzigen.

### Fase P1 — SHADOW intents

- `EM2_Power_Intent` genereren uit bestaande Decision-output;
- EV/WW-targets naast huidige productiecontrol publiceren;
- vergelijken met werkelijk gedrag;
- geen nieuwe fysieke writer.

### Fase P2 — Easee adapter SHADOW

- `EV_target_W` vertalen naar verwachte ampère/fase-instelling;
- resultaat vergelijken met bestaande Tesla-writer;
- deadband/hysterese/rate-limit valideren.

### Fase P3 — Tesla gecontroleerde cut-over

- bestaande Tesla writer blijft de enige fysieke writer;
- input verandert van apparaat-specifieke policy naar `EV_target_W` via adapter;
- regressietest deadline, opportunity, Equalizer, idempotency en restart recovery.

### Fase P4 — boiler adapter

- `WW_target_W` naar binaire bestaande writer;
- comfort/deadline-state-machine blijft ongewijzigd;
- gecontroleerde regressietest.

### Fase P5 — Victron

- batterij direct volgens Power Intent-contract integreren;
- geen tijdelijke tweede batterij-controlarchitectuur bouwen.

## Harde invarianten

1. Energy Core blijft eigenaar van EMS-policy en resourceprioriteit.
2. Per fysieke actuator bestaat exact één automatische writer.
3. Een adapter vertaalt intent, maar neemt geen onafhankelijke prijs/PV/comfort-policybeslissingen.
4. Lokale hardware-safety mag targets altijd begrenzen of weigeren.
5. `0 W` is de canonieke idle-intent.
6. Onbekende/ongeldige State geeft geen opportunistische positieve power intent; control degradeert fail-closed.
7. Iedere intent is revision-consistent met de State/Decision-bron.
8. RC-code wordt niet gewijzigd door deze refactor totdat een afzonderlijke stable/mergebeslissing wordt genomen.

## Eerste implementatiestap

De eerste codewijziging wordt **P1 SHADOW**: uit de bestaande Decision/budget-state een `EM2_POWER_INTENT_V0.1` afleiden en publiceren zonder enige actuatorwrite te veranderen. Pas na vergelijking met huidige Tesla- en WW-control wordt een adapter voor fysieke control kandidaat.
