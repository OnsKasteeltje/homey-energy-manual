# Quooker-regeling

**Status:** 🟢 Actief en end-to-end gevalideerd  
**Regeling:** bestaande Quooker-flows blijven leidend voor fysieke aan/uit-aansturing  
**Detectie:** `EM v2 | 01 Quooker Detector | v0.3 SWITCH-AUTH + P1 HEATING`  
**Publicatie:** Energy Core `EM2_CORE_PUBLISH_V0.10.5`, schema `2.11`

## Doel

De Quooker-integratie maakt onderscheid tussen **beschikbaar/ingeschakeld** en **daadwerkelijk elektrisch verwarmen**, zonder daarvoor zware of frequente volledige Homey-device-snapshots te gebruiken.

De bestaande Quooker-flows blijven de fysieke regeling bepalen. De Energy Core-integratie observeert de toestand en publiceert die voor energiebalans, historie en Live View.

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

## Live View

De Live View toont Quooker als afzonderlijke verbruiker:

- `OFF` → `0 W · uit`;
- `ON_IDLE` → aan/op temperatuur, maar geen actieve energiestroom;
- `HEATING` + vermogen >20 W → actieve energiestroom en werkelijk gedetecteerd vermogen.

Quooker-vermogen wordt één keer van `Overig` afgetrokken. Daardoor blijft de woningbalans sluitend en ontstaat geen dubbeltelling.

## Aansturing

De detector en publicatielaag voeren **geen fysieke Quooker-write** uit. De bestaande Quooker-flows blijven verantwoordelijk voor de fysieke aan/uit-regeling.

> Laatste update: **21 augustus 2026** — switch-authoritative v0.3 + P1 heating assist, historisering, schema 2.11 en Live View-integratie end-to-end gevalideerd.
