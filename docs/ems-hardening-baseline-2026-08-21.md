# EMS hardening — stable baseline 21 augustus 2026

_Status: STABLE / hardeningronde afgerond._

## Doel

Dit document markeert de referentiebaseline na de integrale architectuur-, procesflow- en requirementsregressie van Energy Core v2.

## Actieve kernbaseline

- Core: `EM v2 | 00 Core Tick | v0.10.5`
- Publisher: `EM2_CORE_PUBLISH_V0.10.5`
- Publiek schema: `2.11`
- Contract-aware candidate: `EM v2 | 40 Decision | Contract-aware v0.2`
- WW source advice: `EM v2 | 50 Decision | WW Source Advice v0.1 SHADOW`
- Quooker detector: `EM v2 | 01 Quooker Detector | v0.3 SWITCH-AUTH + P1 HEATING`

## Bindende invarianten

1. **P1 is autoritatief voor netimport/netexport en flexbudget.** `gridMeasurementValid` bestuurt of P1-gebaseerde flexruimte mag worden gebruikt.
2. **Afgeleide PV/huisbalans is diagnostisch.** `derivedHouseBalanceValid=false` of `SOURCE_SKEW` mag een geldige P1-flexbeslissing niet blokkeren.
3. **P1 stale = fail-closed.** Bij ongeldige P1-data wordt het flex-exportbudget 0 W.
4. **Homey-load blijft minimaal.** Eén centrale Core-device-snapshot per vijf minuten; downstream hergebruikt state. Snellere detectie is gericht/event-assisted, niet via korte volledige `getDevices()`-polling.
5. **FIXED/DYNAMIC prijsabstractie is geïsoleerd.** Contract-aware logica leest prijs via `EM2_ContractPrice_*`; legacy M7 is niet de prijsinterface van de nieuwe beslislaag.
6. **Warmwaterbronadvies is shadow-only.** `WW_Boilermodus` blijft productie-leidend totdat een expliciet gevalideerde cut-over wordt besloten.
7. **Victron/Dynamic ESS en Homey hebben gescheiden ownership.** Victron beheert batterij, SOC, laad/ontlaad- en netveiligheid; Homey orchestreert huishoudelijke flexloads en dupliceert geen ESS-safety.
8. **Exact één writer per actuator.** Observatie, historie, website en detectors schrijven niet fysiek tenzij expliciet als writer gevalideerd.
9. **Website/app leest publicatie, niet Homey-devices.** Frontend veroorzaakt geen directe Homey-devicecalls.
10. **Rollback en versiebeheer zijn verplicht.** Een inhoudelijke wijziging krijgt een nieuwe flowversie; vorige versie wordt uitgeschakeld en alleen behouden wanneer rollbackwaarde bestaat.

## Task-7 finding en correctie

Tijdens de regressie bleek `EM v2 | 40 Decision | Contract-aware v0.1` EXPORT/PV-opportunities nog te gaten op de generieke `balanceValid` alias. Omdat deze alias de afgeleide huis/PV-balans representeert, kon `SOURCE_SKEW` ten onrechte een geldige P1-flexopportunity blokkeren.

Correctie:

- `EM v2 | 40 Decision | Contract-aware v0.2` gebruikt `gridMeasurementValid` voor EXPORT/PV-flex;
- `derivedHouseBalanceValid` blijft diagnostisch;
- v0.2 blijft `SHADOW_CANDIDATE` en verricht geen actuatorwrites;
- v0.1 is uitgeschakeld als `[ROLLBACK]`;
- v0.2 is na cut-over succesvol handmatig gestart.

Hiermee is de contract-aware beslislaag weer consistent met de split-validity-architectuur van Core.

## Change gate voor vervolgwerk

Een wijziging is pas een nieuwe stable baseline wanneer ten minste is gecontroleerd:

- geen onbedoelde extra Homey/API-load;
- geen dubbele reader/publisher/writer;
- correcte waarheidsbron en freshness;
- split-validity intact;
- contractabstractie intact;
- comfort/deadline vóór opportunistische optimalisatie;
- Victron/Homey ownership intact;
- schema/revision/publicatie consistent;
- fail-safe gedrag bij stale of ontbrekende data;
- rollbackpad beschikbaar;
- documentatie bijgewerkt.

## Baselinebesluit

Per **21 augustus 2026** is deze hardeningronde afgerond. Deze baseline is het uitgangspunt voor nieuwe functionele uitbreiding; vervolgwijzigingen worden als delta ten opzichte van deze baseline beoordeeld.
