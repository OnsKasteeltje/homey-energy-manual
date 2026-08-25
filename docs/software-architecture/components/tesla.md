---
component: tesla
title: Tesla Charging Controller
version: 2.7.15
status: active
architecture_status: implemented
last_verified: 2026-08-25
source:
  - Homey Advanced Flow: Tesla laden v2.7.15 + RC run lease
  - Homey Advanced Flow: EM v2 | 60 Adapter | EV Power v0.1 SHADOW
  - docs/javascripts/tesla-deadline-controller-v2.8.115.js
  - docs/javascripts/tesla-deadline-core-invariant-v2.8.114.js
---

# Tesla Charging Controller

## Doel

De Tesla-laadfunctie combineert deadline-laden, PV-opportunity laden en contractafhankelijke prijssturing. De productiecontroller is de enige automatische Easee-writer. De nieuwe EV Power Adapter is uitsluitend SHADOW en vertaalt een numeriek vermogensdoel naar een theoretische stroomopdracht zonder fysieke writes.

## Productiepad

De actieve Homey-flow is `Tesla laden v2.7.15 + RC run lease`. Deze draait iedere minuut en kan ook handmatig worden gestart. Voor iedere controller-run wordt eerst een 55-seconden Logic lease verkregen. Een overlappende tweede run wordt overgeslagen.

De productiecontroller leest de Easee charger en P1-meter en gebruikt `target_charger_current` en `onoff` voor fysieke aansturing. Daarmee is dit pad de enige automatische writer naar Easee.

## Deadline-opdracht

Deadline-opdrachten worden gelezen uit `docs/data/tesla-deadline-command.json`. Een nieuwe actieve opdracht bevat ten minste:

- deadline;
- current SOC;
- target SOC;
- doelenergie in kWh;
- maximale laadstroom.

Een deadline in het verleden wordt expliciet geweigerd. Een nieuwe deadline wordt alleen geaccepteerd wanneer de Easee lifetime `meter_power` beschikbaar is; die waarde vormt de immutable calibratiebaseline voor de sessie.

## Deadline-beslisvolgorde

Bij een actieve deadline geldt de volgende prioriteit:

1. Integratie- of energiemeetfout → failsafe stop.
2. Doelenergie bereikt → laden stoppen en lifecycle afsluiten.
3. Tesla niet aangesloten → wachten.
4. Deadline verstreken → catch-up op ingestelde maximale stroom.
5. Latest-start bereikt → catch-up op ingestelde maximale stroom.
6. DYNAMIC + verse GOOD negatieve prijscontext → laden op maximale stroom.
7. Voldoende stabiel direct PV-overschot → opportunity laden op berekende stroom.
8. DYNAMIC + verse GOOD goedkope prijscontext en niet expensive → laden op maximale stroom.
9. DYNAMIC maar prijscontext niet bruikbaar → wachten op prijscontext.
10. Anders wachten.

Voor `FIXED` vindt geen prijsarbitrage plaats. Deadline/MUST en directe P1/PV-opportunity blijven contractonafhankelijk.

## Opportunity zonder deadline

Zonder actieve deadline kan tussen 11:00 en 17:30 direct PV-opportunity laden plaatsvinden. De controller gebruikt een rolling buffer van circa vier minuten en vereist minimaal drie samples over minimaal 115 seconden.

De minimale startgrens is 6 A-equivalent. De gebruikte conversie is 690 W/A. De maximale opportunity-stroom is 11 A. Wanneer de opportunity tijdens laden wegvalt, wordt eerst gedurende 120 seconden bevestigd voordat fysiek wordt gestopt; gedurende deze bevestigingsfase wordt op 6 A gehouden.

## Energiemeting en failsafe

De voorkeursbron voor voortgang is Easee `measure_power`. Wanneer die niet bruikbaar is, kan een P1-delta fallback worden gebruikt mits een geldige baseline bestaat en de berekende Tesla-last binnen plausibele grenzen blijft.

De Easee- en P1-schatting worden onderling gecrosscheckt. Een meetgat groter dan 120 seconden tijdens een actieve deadline veroorzaakt `INTEGRATION_GAP_FAILSAFE`: deadline wordt gedeactiveerd en fysiek laden wordt gestopt.

Wanneer geen geldige energiebron beschikbaar is, geldt `NO_VALID_ENERGY_SOURCE_FAILSAFE`.

## Idempotency

Voor de productiecontroller geldt een 55-seconden run lease met een korte arbitrageperiode. Daardoor kunnen twee vrijwel gelijktijdige starts niet twee controllerexecuties of dubbele fysieke writes veroorzaken.

Binnen `applyTarget()` worden writes bovendien alleen uitgevoerd wanneer de gewenste toestand afwijkt van de actuele toestand. Voor een start op 6 A bestaat een speciale 7 A → 10 s → 6 A bootstrap wanneer de lader uit stilstand moet starten.

## Contract-aware prijscontext

De controller leest uitsluitend:

- `EMS_ContractType`;
- `EM2_ContractPrice_Negative`;
- `EM2_ContractPrice_Cheap_Next4h`;
- `EM2_ContractPrice_Expensive_Next4h`;
- `EM2_ContractPrice_Quality`;
- `EM2_ContractPrice_UpdatedAt`.

Prijsinformatie is alleen bruikbaar wanneer het contract `DYNAMIC` is, quality `GOOD` is en de context maximaal 30 minuten oud is. Legacy M7-prijsinputs worden niet meer gebruikt voor productie-Tesla.

## EV Power Adapter v0.1 SHADOW

`EM v2 | 60 Adapter | EV Power v0.1 SHADOW` is een afzonderlijk toekomstpad. De adapter wordt getriggerd door wijziging van `EM2_Power_Intent` en doet zelf geen device-reads, netwerkcalls of fysieke writes.

De adapter accepteert `EM2_POWER_INTENT_V0.1` of `V0.2`, vereist revision-alignment met `EM2_State`, `intent.valid=true` en `deviceWrites=false`, en vertaalt `target_W` naar `command.value_A`.

W/A wordt bij voorkeur afgeleid uit geobserveerd Tesla-vermogen gedeeld door requested A. Als dat niet beschikbaar is, wordt spanning × aantal actieve fasen gebruikt. Onder de minimale 6 A-deadband wordt de theoretische opdracht 0 A.

De output blijft:

- `readOnly: true`;
- `controlMode: SHADOW`;
- `deviceWrites: false`;
- `physicalWrite: false`.

Dedupe gebeurt op revision + input schema + target_W.

## Frontend en Core-invariant

De websitecontroller `tesla-deadline-controller-v2.8.115.js` valideert invoer vóór versturen, blokkeert deadlines in het verleden en gebruikt een PIN-protected worker-route. Na opslaan wacht de UI maximaal 120 seconden op bevestiging door Core.

`tesla-deadline-core-invariant-v2.8.114.js` handhaaft een harde frontend-invariant: zodra Energy Core meldt dat de deadline terminal/inactief is, mag stale command- of pending-state de UI niet actief houden.

## Outputs

Belangrijke Logic-outputs van de productiecontroller zijn:

- `EV Deadline actief`;
- `EV Deadline tijd`;
- `EV Doel kWh`;
- `EV Max laadstroom A`;
- `EV Deadline status`;
- `EV Geladen kWh`;
- `EV Resterend kWh`;
- `EV Latest start`;
- `EV Deadline Runtime State v2.0`.

## Architectuurgrens

Totdat expliciet gevalideerd en geactiveerd geldt:

- productie `v2.7.15` = enige automatische Easee-writer;
- EV Power Adapter v0.1 = SHADOW translator zonder writes;
- Energy Core en Power Intent mogen dus nog niet rechtstreeks fysieke Easee-aansturing overnemen.

## Validatie-status

De live Homey-flow is enabled en niet broken. RC-idempotency is structureel in de flow ingebouwd via de 55 s lease. De EV Power Adapter is enabled maar expliciet SHADOW.
