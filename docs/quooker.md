# Quooker-regeling

**Status:** 🟢 Actief en end-to-end gevalideerd  
**Regeling:** Pi-planner + Homey Quooker actuator v0.2 LIVE zijn leidend voor fysieke aan/uit-aansturing  
**Detectie:** `EM v2 | 01 Quooker Detector | v0.3 SWITCH-AUTH + P1 HEATING`  
**Publicatie:** Energy Core `EM2_CORE_PUBLISH_V0.10.5`, schema `2.11`

## Doel

De Quooker-integratie maakt onderscheid tussen **beschikbaar/ingeschakeld** en **daadwerkelijk elektrisch verwarmen**, zonder daarvoor zware of frequente volledige Homey-device-snapshots te gebruiken.

Sinds 2 oktober 2026 bepaalt de Pi-planner het Quooker-envelope en voert Homey dit uit via `EM v2 | 60 Actuator | Quooker v0.2 LIVE`. De Energy Core-integratie observeert daarnaast de toestand en publiceert die voor energiebalans, historie en Live View.

## Waarheidsbronnen

De detectie gebruikt twee complementaire bronnen:

1. **Homey Cooker-switch is autoritatief voor aan/uit.**
2. **P1/L3-signatuur is alleen aanvullende bewijsbron voor daadwerkelijk verwarmen en het geschatte Quooker-vermogen.**

Daaruit volgen de statussen:

| Switch | P1/L3 heating-signatuur | Status | `active` |
|---|---|---|---|
| uit | n.v.t. | `OFF` | `false` |
| aan | niet aanwezig | `ON_IDLE` | `false` |
| aan | aanwezig | `HEATING` | `true` |

`active=true` betekent dus specifiek **daadwerkelijk verwarmen**, niet alleen dat de Quooker-schakelaar aanstaat.

## Lichte detectieroute

De detector gebruikt geen volledige `getDevices()`-snapshot. Per evaluatie wordt alleen de Cooker gericht gelezen. Alleen wanneer sinds de vorige evaluatie een relevant P1-event is ontvangen, wordt aanvullend één gerichte P1-read uitgevoerd.

```text
Homey Cooker switch ───────────────► OFF / ON_IDLE
                                         │
P1/L3 event ─► gerichte P1-read ─────────┴──► HEATING + power_w
```

Dit volgt de architectuurregel: bestaande status direct gebruiken en P1 alleen inzetten voor informatie die de switch niet kan leveren.

## Publicatiecontract

`loads.quooker` publiceert minimaal:

```text
switch_on
active
power_w
status
fresh
last_sample_at
source = HOMEY_SWITCH_PLUS_P1_L3
last_transition
last_heating_at
last_heating_power_w
transition_history
```

Korte statusovergangen blijven daardoor achteraf bewijsbaar zonder extra devicepolling.

## Historisering

De detector bewaart een beperkte rolling transition history. Relevante velden zijn:

- `last_transition`;
- `last_heating_at`;
- `last_heating_power_w`;
- `transition_history` (beperkte recente reeks).

Historisering gebruikt de reeds gedetecteerde toestand en veroorzaakt geen aanvullende Homey-device-scans.

## End-to-end validatie 21 augustus 2026

De nieuwe route is fysiek gevalideerd met een echte Quooker-opwarming. De gedetecteerde reeks was:

```text
OFF → ON_IDLE → HEATING → ON_IDLE
```

Tijdens `HEATING` werd op L3 circa **1.621 W** gezien. Na baselinecorrectie werd circa **1.579 W** als Quooker-vermogen gepubliceerd. Daarna bleef de switch aan terwijl de status correct terugging naar `ON_IDLE` en `active=false`.

Hiermee zijn switchstatus, P1-heatingdetectie, historisering, Core-publicatie en Live View-contract end-to-end bewezen.

## Historische planner-calibratie 30 september 2026

De historische legacy-aanmomenten zijn gebruikt als ground-truth om de Quooker-opwarming uit totaal-P1 te herkennen. Een bekende Cooker OFF→ON-overgang gecombineerd met een korte P1-uptick rond de eerder gevalideerde ~1,58 kW heating-signatuur is voldoende voor energie-attributie; aparte L3-bevestiging is daarbij ondersteunend maar niet vereist.

Over 6–30 september 2026 leverde de conservatief geselecteerde set normale cycli een centrale waarde rond **0,25–0,26 kWh per opwarming**. Voor de planner is dit afgerond naar een dagelijks **0,25 kWh energy-budget**. Bij 15-minuten-planslots is dat gelijk aan **1000 W gemiddeld in één forced-slot**. Het fysieke verwarmingsvermogen blijft circa **1580 W**, equivalent aan ongeveer **9,5 minuut** verwarmen voor 0,25 kWh.

Plannerregel:

- energy-budget: `0.25 kWh`;
- forced planning-equivalent: `1000 W` in één 15-minuten-slot;
- instantaneous heating/headroom: `1580 W`;
- de resterende forced-slots reserveren geen tweede, derde of vierde 0,25 kWh;
- realtime `OPPORTUNITY`/`FORCED_ON` control-envelope blijft afzonderlijk van deze energieboekhouding.

## AI / historische actuator-evidence

De control-neutrale Quooker evidence-push naar de Pi bewaart het actuatorcontract versiegetrouw. Historische v0.1-events blijven herkenbaar als `mode=SHADOW` met `actualOn`/`wouldWrite`. Voor de huidige v0.2 LIVE-actuator worden `mode=LIVE`, `actualOnBefore`, `actualOnAfter`, `physicalWritePerformed` en `writeError` vastgelegd.

`physicalWritePerformed=true` is direct bewijs dat de Homey-actuator een Cooker-device-write heeft uitgevoerd. `false` kan bij LIVE juist een correcte idempotente no-op betekenen wanneer de gewenste en actuele toestand al gelijk waren. De detectorstatus `HEATING` blijft afzonderlijk bewijs van elektrisch verwarmen en mag zonder actuatorbewijs niet als fysieke EMS-write worden geïnterpreteerd.

De analyse-reader kan voor reeds vóór 4 oktober 2026 volgens het oude normalisatieschema opgeslagen v0.2-events de originele `raw_json` gebruiken om expliciete LIVE-velden terug te halen; ontbrekende actuator-mode wordt nooit uit HEATING afgeleid.

## Live View

De Live View toont Quooker als afzonderlijke verbruiker:

- `OFF` → `0 W · uit`;
- `ON_IDLE` → aan/op temperatuur, maar geen actieve energiestroom;
- `HEATING` + vermogen >20 W → actieve energiestroom en werkelijk gedetecteerd vermogen.

Quooker-vermogen wordt één keer van `Overig` afgetrokken. Daardoor blijft de woningbalans sluitend en ontstaat geen dubbeltelling.

## Aansturing

De detector en publicatielaag voeren **geen fysieke Quooker-write** uit. De fysieke write is exclusief eigendom van `EM v2 | 60 Actuator | Quooker v0.2 LIVE` (Flow ID `2d0ca017-0d35-4071-bd06-87742032c399`). De drie oude tijdflows zijn disabled en dienen alleen als rollback-evidence.

> Laatste update: **4 oktober 2026** — Quooker actuator v0.2 LIVE blijft sole physical writer; AI/evidenceketen is LIVE-actuator-aware en behoudt expliciet physical-write bewijs.
