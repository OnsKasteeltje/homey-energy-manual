# Power Intent Layer v0.2

## Status

**Branch:** `main`  
**Fase:** P1/P2 SHADOW  
**Fysieke actuatorwijzigingen:** geen  
**RC-impact:** geen; `rc-2026-08-24` blijft onaangetast  
**EV-adapter:** `EV_POWER_ADAPTER_V0.1`, `deviceWrites=false`

## Doel

De Power Intent Layer maakt de scheiding expliciet tussen **EMS-besluitvorming** en **apparaat-specifieke actuatie**.

De Energy Core beslist in functionele vermogensintenties in watt. Alleen een actuator-adapter vertaalt die intentie naar een technisch uitvoerbare apparaatopdracht. Een adapter mag een target vanwege fysieke of veiligheidsconstraints begrenzen of weigeren, maar mag nooit zelfstandig extra EMS-policy introduceren of méér vermogen claimen dan upstream is toegewezen.

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

Homey ondersteunt native `target_power` en `target_power_mode`. Dit wordt gebruikt als referentiesemantiek en waar betrouwbaar mogelijk als native capability, conform guardrail G1.

`target_power_mode=homey` maakt Homey's generieke Energy-logica niet tot eigenaar van onze EMS-policy. Energy Core blijft de arbiter voor deadlines, contracttype, comfort, PV-budget en prioriteiten. De native capability is een actuator-/capability-interface, geen vervanging van de Energy Core.

## Canonieke tekenconventie

```text
+W = verbruik / laden uit AC-zijde
 0 = idle / geen vermogensvraag
-W = teruglevering / ontladen naar AC-zijde
```

Voorbeelden:

```text
EV_target_W       = +6200
WW_target_W       = +1900
Battery_target_W  = -2500
Battery_target_W  = +2500
```

Adapters mogen deze semantiek intern naar apparaat-specifieke tekenconventies vertalen, maar de betekenis aan de Core-grens blijft apparaat-onafhankelijk.

## Resource-intents

### Tesla / EV

Tesla/Easee is een variabele flexload. De Core publiceert uitsluitend `EV_target_W`; legacy `requested_A` is geen upstream control-contract.

EV Power Adapter v0.1 is bewust beperkt tot de huidige gevalideerde laadtopologie:

```text
phaseCount   = 3
voltageV     = 230
minCurrentA  = 6
maxCurrentA  = expliciete veilige configuratie
phaseSwitch  = disabled
```

De deterministische vertaling is:

```text
theoretical_A = EV_target_W / (phaseCount × voltageV)
requested_A   = floor(theoretical_A)
requested_A   = min(requested_A, floor(maxCurrentA))

if requested_A < minCurrentA:
    requested_A = 0
```

Er wordt **naar beneden gekwantiseerd**, zodat de adapter het upstream toegekende vermogensbudget nooit overschrijdt. Een positieve intent onder het minimale uitvoerbare 3-fasevermogen wordt niet omhoog afgerond naar 6 A, maar fail-closed naar 0 A met `BELOW_MINIMUM_EXECUTABLE_POWER`.

Bij 3 × 230 V geldt daardoor onder meer:

| `EV_target_W` | `requested_A` | `executable_W` |
|---:|---:|---:|
| 4.139 W | 0 A | 0 W |
| 4.140 W | 6 A | 4.140 W |
| 6.200 W | 8 A | 5.520 W |
| 6.210 W | 9 A | 6.210 W |

De adapter bewaakt daarnaast lokale fysieke constraints, input-freshness en charger-beschikbaarheid. Easee Equalizer en andere hardware-safety blijven hoger in de veiligheidshiërarchie en mogen de uitvoering verder begrenzen.

### EV fail-closed contract

De EV-adapter geeft `requested_A=0` wanneer minimaal één control-critical voorwaarde niet betrouwbaar is, waaronder:

- intent ontbreekt, ongeldig of negatief is;
- intent ouder is dan de vastgelegde freshness-limiet;
- charger niet beschikbaar is;
- charger-state ontbreekt of stale is;
- elektrische constraints ongeldig of intern inconsistent zijn;
- `maxCurrentA` onder `minCurrentA` ligt;
- een toekomstige state of capability niet expliciet ondersteund wordt.

Stale of out-of-order device-events mogen geen actuele bevestigde state overschrijven.

### Requested, commanded en confirmed

Een gewenste hardwarewaarde is niet hetzelfde als een uitgevoerde hardwarewaarde. Het control-contract onderscheidt daarom expliciet:

```text
requested_A  = deterministisch berekende adapteroutput
commanded_A  = waarde waarvoor de writer daadwerkelijk een write heeft gestart
confirmed_A  = door charger/runtime terugbevestigde actuele waarde
```

Een API/HTTP-acceptatie is geen fysieke bevestiging. In SHADOW blijft `commanded_A=null`; `confirmed_A` mag read-only worden gebruikt voor vergelijking en validatie.

### Easee write-semantiek

Wanneer later LIVE wordt geschakeld, mag hoogfrequente EMS-regeling uitsluitend een **dynamic/volatile Easee current-control path** gebruiken. Persistente/non-dynamic max-current- of configuratie-instellingen zijn geen runtime-actuatorinterface en mogen niet als frequente EMS-write worden ingezet.

Deze eis is een harde LIVE release-gate.

### Automatische faseschakeling

Automatische 1↔3-faseschakeling is **geen onderdeel van EV Power Adapter v0.1**. Een toekomstige implementatie moet als expliciete state machine worden ontworpen:

```text
ZERO / stop charging
      ↓
bevestig dat laadvermogen nul is
      ↓
dead-time
      ↓
phase switch
      ↓
bevestig target phase
      ↓
restart op minimaal uitvoerbaar setpoint
      ↓
NORMAL
```

De state machine moet een timeout/failure-state hebben. Faseschakeling mag nooit als een losse stateless current-write worden toegevoegd.

### Warm water / boiler

De boiler is praktisch een binaire flexload:

```text
WW_target_W = 0      → OFF
WW_target_W ≈ 1900   → ON
```

De boiler-adapter vertaalt de intentie naar de bestaande gevalideerde ON/OFF-writer. Er wordt geen fictieve vermogensmodulatie geïntroduceerd. Comfort-, deadline- en minimum-runtimepolicy blijven upstream en/of in de bestaande expliciete boiler-state-machine, niet in een generieke W→ON/OFF mapper.

### Victron / batterij

Na fysieke integratie wordt de batterij de eerste bidirectionele resource:

```text
Battery_target_W > 0  → laden
Battery_target_W = 0  → idle
Battery_target_W < 0  → ontladen
```

De Victron-adapter vertaalt dit naar de gekozen ESS/Modbus-interface. BMS/ESS/safety-regels mogen targets begrenzen of weigeren, maar de adapter introduceert geen prijs/PV-policy.

## Arbiter en budget

De centrale vermogensbudgettering blijft leidend. De som van discretionaire positieve intents mag nooit meer claimen dan het door policy vrijgegeven budget, behalve voor expliciete MUST/deadline-loads waarvoor de Core gecontroleerde import heeft toegestaan.

Een actuator-adapter mag het toegewezen target **verlagen of nul maken** door uitvoerbaarheidsconstraints, maar nooit verhogen. Quantisatieverlies wordt expliciet als `deltaW` gepubliceerd.

## Deterministische adapter versus policy-stabilisatie

De actuator-adapter zelf blijft zo veel mogelijk een pure, deterministische mapping:

```text
fresh intent + fresh device constraints
      ↓
validation
      ↓
physical feasibility
      ↓
quantize/clamp down
      ↓
requested actuator state
```

PV-smoothing, hysterese, minimale stabiele duur, opportunity/MUST-prioriteit en andere tijdsafhankelijke EMS-beslissingen horen **upstream in Energy Core / policy**. Daarmee blijft de adapter reproduceerbaar en unit-testbaar.

Technische eigenschappen die wél adapter-eigendom zijn, zijn minimaal uitvoerbaar vermogen, fysieke min/max, capability-detectie, freshness, quantisatie, unsupported-state rejection en actuator-state-confirmatie.

## Idempotency en write-discipline

Idempotency, run-lease, dedup, rate limiting en single-writer blijven verplicht rond de writer. Een write wordt alleen gestart wanneer de gewenste uitvoerbare actuatorstate relevant afwijkt van de laatst bevestigde/commanded state en de writer-gate dit toestaat.

Deze stateful write-discipline wordt niet verstopt in de pure W→A-mapper.

## EV SHADOW output v0.1

De uitvoerbare referentie-implementatie staat in `docs/javascripts/ev-power-adapter-shadow-v0.1.js` en publiceert conceptueel:

```json
{
  "schema": "EV_POWER_ADAPTER_V0.1",
  "mode": "SHADOW",
  "deviceWrites": false,
  "targetW": 6200,
  "theoreticalA": 8.9855,
  "requestedA": 8,
  "executableW": 5520,
  "deltaW": -680,
  "reason": "QUANTIZED_DOWN",
  "inputFresh": true,
  "chargerState": "plugged_in",
  "commandedA": null,
  "confirmedA": null,
  "sourceRevision": 0,
  "timestamp": "..."
}
```

`deviceWrites=false` is hard-coded in v0.1 en kan niet door input worden aangezet.

## Canonieke Power Intent state

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

### P0 — architectuur
Interface en tekenconventie vastleggen; geen actuatorwrites wijzigen.

### P1 — SHADOW intents
`EM2_Power_Intent` genereren uit bestaande Decision/budget-state; EV/WW-targets naast productiecontrol publiceren; geen nieuwe fysieke writer.

### P2 — EV Power Adapter SHADOW
`EV_target_W` deterministisch naar theoretisch uitvoerbare 3-fase Easee-opdracht vertalen; freshness en constraints valideren; requested-versus-confirmed vergelijken; `deviceWrites=false`.

### P3 — Tesla gecontroleerde cut-over
Pas na expliciete LIVE-gates: dynamic/volatile Easee write-path bewezen, freshness/fail-closed bewezen, requested/commanded/confirmed lifecycle bewezen, idempotency/restart recovery groen en single-writer behouden.

### P4 — boiler adapter
`WW_target_W` naar de bestaande binaire writer; comfort/deadline-state-machine blijft beleidsmatig intact.

### P5 — Victron
Batterij direct volgens hetzelfde Power Intent-contract integreren; geen tijdelijke tweede controlarchitectuur.

## Harde invarianten

1. Energy Core blijft eigenaar van EMS-policy en resourceprioriteit.
2. Per fysieke actuator bestaat exact één automatische writer.
3. Een adapter vertaalt intent en fysieke constraints, maar neemt geen onafhankelijke prijs/PV/comfort/deadline-policybeslissingen.
4. Een adapter mag een upstream vermogensbudget nooit verhogen; alleen gelijk houden, naar beneden kwantiseren, begrenzen of nul maken.
5. Lokale hardware-safety mag targets altijd begrenzen of weigeren.
6. `0 W` is de canonieke idle-intent.
7. Ongeldige of stale control-state degradeert fail-closed.
8. Requested, commanded en confirmed actuatorstate zijn afzonderlijke begrippen.
9. Hoogfrequente device-control gebruikt alleen interfaces die daarvoor technisch bedoeld zijn; voor Easee betekent dit dynamic/volatile control.
10. Stateful transities zoals faseschakeling worden als expliciete state machine gemodelleerd.
11. Iedere intent is revision-consistent met de State/Decision-bron.
12. RC-code wordt niet gewijzigd door deze refactor totdat een afzonderlijke stable/mergebeslissing wordt genomen.

## Validatie

`tests/ev-power-adapter-shadow.test.mjs` bevat boundary- en invarianttests voor onder meer 0 W, 4.139/4.140 W, 6.200/6.210 W, max-current clamp, stale intent, stale charger-state, charger unavailable en de invariant dat `executableW <= EV_target_W` over het geteste bereik.
