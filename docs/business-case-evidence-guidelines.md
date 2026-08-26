# Business Case Evidence Hardening Guidelines

Deze regels vormen een bindende aanvulling op de Business Case Engineering Guidelines voor historische prijzen, high-resolution evidence, CAPEX, forecast-replay en batterijcalibratie.

## B18 — Historisch tarief is timestamped evidence

Iedere historische BC-tijdstap gebruikt primair het tarief dat op dat moment aantoonbaar beschikbaar/geldig was. De resolver:

- kiest uitsluitend een tarief met `tariffAt <= sample.ts`;
- gebruikt geen toekomstig prijsrecord om een oudere tijdstap te waarderen;
- accepteert alleen expliciet geldige/GOOD historische prijsdata als primaire bron;
- bewaart `contractType`, bron, quality, tariff timestamp en age als provenance;
- gebruikt een vaste/configuratieprijs alleen als expliciet gemarkeerde fallback;
- behandelt ontbrekende/stale prijsdata als unknown wanneer geen toegestane fallback bestaat.

`contract-history-v01.json` is de primaire historische prijsbron voor bestaande FIXED/DYNAMIC contractcontext. Een contractwisseling hoeft daardoor niet achteraf handmatig in een jaarmodel te worden gereconstrueerd.

## B19 — Rolling UI-history is geen investerings-evidence store

De 7-daagse full-resolution file blijft een snelle presentation-/diagnostic store. Voor de BC geldt aanvullend:

- afgeronde 5-minutendagen worden per kalenderdag immutable opgeslagen;
- een afgesloten dagbestand wordt niet in-place herschreven door normale collectie;
- een index bewaart datum, pad, sample-count en archive timestamp;
- retentie is minimaal één representatief jaar; huidige target is 400 dagen;
- `NULL_IS_UNKNOWN_NEVER_ZERO` en measurement-validity blijven behouden;
- een backfill mag alleen uit reeds bestaande canonieke history komen en mag geen meetwaarden reconstrueren die nooit zijn vastgelegd.

## B20 — CAPEX heeft evidence en completeness

CAPEX wordt component-gebaseerd en versioned vastgelegd. Verplicht:

- exact product/model waar relevant;
- waarnemingsdatum en bron per prijs;
- meerdere actuele prijsobservaties wanneer materieel mogelijk;
- onderscheid tussen reeds aanwezig/sunk, nog aan te schaffen hardware, balance-of-system en installatie/self-install;
- `knownIncrementalHardwareEuro` mag worden gepubliceerd voordat de totale investering compleet is;
- NPV/payback/IRR mogen niet als definitieve financiële KPI worden berekend zolang `completeCapexEuro` ontbreekt;
- een laagste internetprijs wordt niet automatisch de canonieke referentieprijs.

## B21 — Forecast-realistic evidence wordt bij issuance opgeslagen

Een forecast-realistic replay mag voorspellingen niet achteraf reconstrueren uit gerealiseerde data. Daarom wordt minimaal per 15 minuten bewaard:

- planner generation timestamp/schema;
- het toen geldende plan-slot;
- forecast PV en prijscontext indien aanwezig;
- geplande EV/WW/batterijtargets en reason;
- Power Intent schema/sourceRevision/validity;
- actuele EV/WW/batterij-intents;
- writeAllowed/control-mode context.

De collector gebruikt bestaande Logic/plannerpublicaties en introduceert geen nieuwe device-polling. Dagdata wordt eerst restart-persistent gebufferd en na afsluiten immutable gearchiveerd.

## B22 — Victron calibration is evidence-gated

Na fysieke Victron-integratie wordt generieke batterijmodellering gehard met echte runtime-evidence. Minimaal:

- AC battery power + SOC + timestamp/validity;
- bij voorkeur DC battery power voor gescheiden charge/discharge-efficiency;
- expliciete system-loss/idle telemetry voor standby; standby wordt niet uit een onverklaarde energiebalans verzonnen;
- minimale coverage en throughput voordat calibration als `GOOD` geldt;
- round-trip efficiency alleen over voldoende gesloten SOC-vensters;
- iedere calibration candidate bewaart coverage, throughput en quality;
- promotie naar scenario-aannames gebeurt nooit automatisch en vereist expliciete review/version update.

## B23 — Evidencecollectoren blijven buiten control

BC-collectoren en calibrators zijn observe-only/read-only ten opzichte van energieactuatie:

- geen actuatorwrites;
- geen wijziging van Power Intent;
- geen extra full-device polling wanneer bestaande state/publicaties voldoende zijn;
- GitHub/Logic writes zijn uitsluitend evidence-persistence;
- collector failure mag geen realtime EMS-control blokkeren of veranderen.

## Acceptatiecriterium

Een batterij-BC is niet `INVESTMENT_READY` zolang minimaal één van de volgende punten materieel ontbreekt: representatieve high-resolution history, tijdcorrecte tariff evidence, complete CAPEX, reproduceerbare scenario-constraints of voldoende calibration/sensitivity voor de gebruikte aannames.
