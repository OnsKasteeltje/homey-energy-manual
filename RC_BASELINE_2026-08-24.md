# Release Candidate baseline — 2026-08-24

Status: **RC GO / frozen baseline**

## Baseline

- Branch: `rc-2026-08-24`
- Baseline source commit: `7316ce172b266648b81bda1e9862b01b89e8279c`
- Energy Core publication at branch creation: **revision 1980**
- Baseline date: 2026-08-24 (Europe/Berlin)

## RC hardening gates

De RC is aangemaakt nadat de afgesproken hardening-gates expliciet als PASS waren afgerond.

1. **Reboot/restart recovery — PASS**
   - `EMS_ContractType` komt na restart/reboot zonder handmatige reparatie terug.
   - `WW_Boilermodus` komt zonder handmatige reparatie terug.
   - Tesla lifecycle-state herstelt correct.
   - notificatie-dedup state blijft correct en veroorzaakt geen dubbele notificaties.

2. **Idempotency / double-start — PASS**
   - vrijwel gelijktijdige starts leiden via de run-lease tot maximaal één effectieve controllerexecutie;
   - geen dubbele fysieke Easee-writes;
   - geen dubbele notificaties;
   - geen dubbele history-records.

## Freeze-scope

Deze RC bevat uitsluitend de huidige bewezen productie- en SHADOW-functionaliteit zoals aanwezig in de baselinecommit.

Niet opnemen in deze RC:

- Homey `target_power` / `target_power_mode` refactoring;
- Power Intent Layer;
- nieuwe actuator-adapters voor Easee/boiler/Victron;
- overige nieuwe architectuurverbeteringen die niet nodig zijn voor een RC-fix.

Deze onderwerpen zijn post-RC werk.

## Architectuurguardrails

De volgende regels gelden ook tijdens RC-hardening en eventuele RC-fixes:

- **Native-first:** bouw geen functie zelf die Homey betrouwbaar native kan leveren, tenzij EMS-semantiek, reproduceerbaarheid/determinisme, fail-safe gedrag of observability een eigen implementatie vereist.
- **Single-controller/single-writer:** geen externe app, plugin, flow of integratie mag een tweede zelfstandig beslis- of schrijfpunt voor dezelfde fysieke actuator introduceren.
- Een RC-fix mag geen nieuwe functionele scope introduceren.

## Change policy

Na deze baseline is de branch functioneel bevroren. Alleen aantoonbare RC-defectfixes zijn toegestaan. Elke fix vereist gerichte regressie op het geraakte pad en mag geen post-RC refactoring meenemen.
