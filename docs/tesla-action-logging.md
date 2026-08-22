# Tesla Action Log en Opportunity Cycle Evaluator

_Status: IMPLEMENTED / VALIDATION — 22 augustus 2026_

## Doel

Tesla opportunity charging wordt niet op basis van één geslaagde start vrijgegeven. De regeling moet over meerdere echte laadcycli aantoonbaar correct starten, opregelen, afregelen, pauzeren en opnieuw starten zonder ongewenste netimport of oscillatie.

Daarom draait naast de productiecontroller een aparte observatielaag:

- productie: `Tesla laden v2.7.10`;
- validatie: `EM v2 | 80 Validation | Tesla Action Log v0.1`.

De validatielaag is logic-only. Zij doet geen `Homey.devices.getDevices()`, leest P1/Easee niet opnieuw en doet geen actuatorwrites. Zij consumeert uitsluitend de reeds door de Tesla-controller opgebouwde `EV Deadline Runtime State v2.0`.

## Actielog

Homey Logic variabele: `EV Tesla Action Log v1`.

Alleen wijzigingen van de gevraagde laadstroom worden als actie vastgelegd. Actietypen:

- `START`: 0 A -> >0 A;
- `INCREASE`: hogere doelstroom;
- `REDUCE`: lagere doelstroom;
- `PAUSE`: >0 A -> 0 A.

Redencategorieën:

- `OPPORTUNITY` — PV-/exportgestuurde laadactie;
- `DEADLINE` — deadline/MUST-gedreven laadactie;
- `SAFETY` — failsafe/geblokkeerde actie;
- `MANUAL` — gereserveerd voor expliciet gemarkeerde handmatige acties.

Per actie worden onder meer opgeslagen: tijdstip, reden, actie, `from_a`, `to_a`, controllerstatus, P1 vóór actie, Easee-laadvermogen vóór actie en beschikbaar PV-surplus. Op de eerstvolgende verse controller-runtime wordt de reactie gekoppeld met P1 na actie, Easee-vermogen en resultaat.

Resultaten:

- `PASS` — actuatorrespons en P1-reactie plausibel;
- `OVERSHOOT` — opportunity-actie resulteert in >750 W netimport;
- `NO_RESPONSE` — verwachte start/stop is fysiek niet zichtbaar.

De log is begrensd op de laatste 120 acties zodat Homey Logic-state niet onbeperkt groeit.

## Opportunity Cycle Evaluator

Homey Logic variabele: `EV Opportunity Cycles v1`.

Een opportunity-cyclus begint bij een `OPPORTUNITY START` vanaf 0 A en eindigt wanneer een opportunity-pauze op de volgende verse runtime als daadwerkelijk gestopt wordt bevestigd.

Per cyclus worden minimaal bijgehouden:

- start- en eindtijd;
- startstroom en maximale laadstroom;
- maximale ongewenste netimport;
- aantal importsamples boven 750 W;
- aantal regelacties;
- aantal runtimesamples;
- geschatte geladen kWh uit de reeds gemeten Easee-vermogenssamples;
- eindresultaat.

Maximaal 20 afgeronde cycli worden bewaard.

## DoD voor opportunity charging

De logger geeft `ready_for_dod=true` pas wanneer minimaal vijf volledige opportunity-cycli beschikbaar zijn en in de geëvalueerde acties geen `OVERSHOOT` of `NO_RESPONSE` voorkomt.

Dit is een minimumgate, geen automatische productievrijgave. Voor VERIFIED moeten de vijf cycli ook inhoudelijk voldoende variatie bevatten: starten vanaf pauze, opregelen, terugregelen bij dalend surplus, pauzeren bij onvoldoende surplus en minimaal één correcte herstart na een eerdere pauze/wolk.

## Architectuurgrens

De logger is uitsluitend observability/validation. Resultaten uit `EV Tesla Action Log v1` of `EV Opportunity Cycles v1` mogen niet rechtstreeks terug de fysieke control-loop in. Aanpassingen aan startstroom, rampsnelheid of hysterese worden apart/versioned in de Tesla-productiecontroller aangebracht en daarna opnieuw met deze logger gevalideerd.

## Bekend open punt — MANUAL

De actieve handmatige Homey start/stop-flows schrijven rechtstreeks naar Easee en zijn nog niet allemaal voorzien van een gestandaardiseerde manual-intent marker. De enum `MANUAL` bestaat al, maar volledige betrouwbare bronattributie van legacy handmatige flows blijft daarom een aparte hardeningstap. Tot die instrumentatie is afgerond, mag een extern handmatig gewijzigde Easee-doelstroom niet automatisch als bewezen `MANUAL` worden geïnterpreteerd.
