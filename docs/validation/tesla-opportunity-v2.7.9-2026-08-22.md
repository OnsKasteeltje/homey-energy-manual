# Tesla opportunity-validatie — v2.7.9

Datum: 2026-08-22
Status: **PASS — eerste end-to-end opportunity-start gevalideerd**

## Waarneming

Na afronding van de deadline-laadactie stond de Tesla/Easee-keten in gepauzeerde toestand zonder actieve laadstroom. De Tesla-controller `Tesla laden v2.7.9` kon daardoor de normale PV-opportunitymodus gebruiken.

Bij voldoende en stabiel PV/netto-exportsurplus is de Tesla vervolgens **zelfstandig gestart met laden op 7 A**. De gebruiker bevestigde de daadwerkelijke laadstart.

## Gevalideerde keten

`P1 netto-export -> Homey Tesla-controller v2.7.9 -> opportunity-beslissing -> Easee Charger -> Tesla`

Resultaat: **end-to-end functioneel**.

## Relevante eigenschappen v2.7.9

- Deadline-control heeft prioriteit wanneer een deadline actief is.
- Zonder actieve deadline kan PV-opportunityladen zelfstandig overnemen.
- Opportunity gebruikt een stabiliteitsvenster in plaats van direct op een losse exportpiek te reageren.
- Beschikbaar surplus wordt gereconstrueerd met Tesla-laadvermogen zodat het starten van de Tesla het regelsignaal niet kunstmatig laat instorten.
- De anti-oscillatie/kickstart-benadering uit de eerdere werkende Homey Tesla-flow is hergebruikt.

## Geobserveerde start

- Easee/Tesla vóór start: aangesloten en gepauzeerd, 0 A.
- Opportunity-start: **7 A**.
- Start vond autonoom plaats zonder actieve deadline.

## Conclusie

Dit is het eerste gevalideerde praktijkbewijs dat `Tesla laden v2.7.9` na een deadline terugvalt naar normale opportunity-control en vervolgens zelfstandig een PV-gebaseerde laadactie kan starten. Hiermee is de volledige opportunity-keten voor de startconditie gevalideerd.

Nog apart te valideren in volgende praktijksituaties: terugregelen bij dalend surplus, stoppen bij onvoldoende surplus, opnieuw starten na bewolking en correcte overgang van opportunity naar een nieuwe deadline.
