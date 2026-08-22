# Tesla opportunity-validatie — v2.7.10

Datum: 2026-08-22  
Status: **PARTIAL PASS — closed-loop werkt, initiële ramp overshoot; nog niet VERIFIED**

## Praktijkproef

Testconditie: Tesla aangesloten, circa 50% SOC, laadlimiet 90%, geen actieve deadline/MUST. Doel was de normale PV-opportunityregeling end-to-end te observeren.

### 1. Startconditie

Vóór start:

- Easee `Paused / plugged_in_paused`;
- 0 A / 0 W;
- P1 circa 8,53 kW netto export.

De Tesla-controller startte autonoom. Dit bevestigt opnieuw dat de keten P1 -> Homey Tesla-controller -> Easee -> Tesla functioneert zonder deadline.

### 2. Te agressieve eerste ramp

De controller ging naar 3x11 A:

- Easee doel/aangeboden: 11 A;
- werkelijk circa 11,03 / 11,14 / 11,16 A;
- laadvermogen circa 7,95 kW;
- gebruiker observeerde tijdelijk circa 4 kW netimport;
- een gecontroleerde P1-read daarna gaf nog circa +1,98 kW netimport.

Beoordeling: **FAIL / OVERSHOOT** voor de initiële ramp. Het vóór-start beschikbare exportbudget mag niet rechtstreeks tot een grote stroomstap leiden zonder eerst nieuwe P1-feedback na de start af te wachten.

### 3. Closed-loop terugregelen

Daarna regelde de controller terug:

- 11 A -> 10 A;
- bij 10 A circa 7,27 kW laadvermogen;
- P1 circa -0,24 kW, dus weer lichte export;
- vervolgens werd circa 3x8 A geobserveerd en als stabiel ervaren.

Beoordeling: **PASS** voor closed-loop correctie na de overshoot.

### 4. Pauzeren bij onvoldoende surplus

Later stopte de laadactie volledig:

- Easee `Paused / plugged_in_paused`;
- 0 A / 0 W;
- P1 circa 2,57 kW export;
- Equalizer circa 2,33 kW export.

Omdat 3-fase 6 A grofweg 4,1–4,3 kW vraagt en 7 A circa 4,8–5,0 kW, was dit surplus onvoldoende voor verantwoord laden.

Beoordeling: **PASS** voor pauzeren bij onvoldoende surplus.

## Voorlopige conclusie

| Gedrag | Resultaat |
|---|---|
| autonoom starten zonder deadline | PASS |
| initiële ramp | FAIL — overshoot |
| terugregelen 11 -> 10 -> circa 8 A | PASS |
| pauzeren bij onvoldoende surplus | PASS |
| herstart na pauze/wolk | OPEN |
| opportunity -> nieuwe deadline | OPEN |

Opportunity charging is daarom **niet VERIFIED**.

## Afgesproken vervolgrichting

Kandidaat voor volgende productieversie, apart te implementeren en valideren:

1. vanuit 0 A starten op 7 A;
2. minimaal één verse P1-feedbackcyclus afwachten;
3. vervolgens maximaal 1 A per normale feedbackcyclus op- of afregelen;
4. bij forse import sneller 2 A terug mogen regelen;
5. onder de minimale veilige surplusgrens pauzeren;
6. herstart opnieuw via dezelfde gecontroleerde 7 A-ramp.

Deze controlwijziging is in deze validatienotitie **nog niet als geïmplementeerd** gemarkeerd.

## Nieuwe observatielaag

Na deze proef is `EM v2 | 80 Validation | Tesla Action Log v0.1` toegevoegd. Deze logic-only flow leest alleen `EV Deadline Runtime State v2.0` en bouwt `EV Tesla Action Log v1` en `EV Opportunity Cycles v1` op. De productiecontroller `Tesla laden v2.7.10` blijft tijdens deze stap onaangeraakt en de enige automatische Easee-writer.

Zie `docs/tesla-action-logging.md` voor schema, resultaten en DoD-gate.
