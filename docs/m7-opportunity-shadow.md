# M7 – Opportunity Score Shadow

**Status:** 🟡 Actief in shadow mode  
**Actieve flow:** `M7 - Opportunity Score - Shadow v1.3`  
**Vorige versie:** `M7 - Opportunity Score - Shadow v1.2` (uitgeschakeld)

De flow draait iedere 15 minuten en stuurt geen apparaten aan.

## Doel
Deze flow onderzoekt onafhankelijk of prijs- en PV-forecastinformatie daadwerkelijk extra waarde toevoegt aan de bestaande Energy Manager. Hij draait parallel aan de baseline/shadowflow en verandert die dataset niet.

## Trigger
Iedere 15 minuten.

## Inputs
- vier gedeelde Homey Logic-booleans uit M7 Prijs & PV Forecast;
- P1/netpositie;
- Tesla/Easee-status en laadvermogen;
- de semantische boilerstatus uit de Energy Manager en het actuele boilervermogen;
- Quookerstatus.

De vier contextvariabelen zijn `M7_Price_Negative`, `M7_Price_Cheap_Next4h`, `M7_Price_Expensive_Next4h` en `M7_PV_Top4h`.

De gevalideerde boilerstatus wordt gelezen uit de meest recente publicatie in `docs/data/shadow-baseline-v01.json`. M7 dupliceert de boiler-state-machine dus niet.

## Logica
De flow berekent een **Opportunity Score** en vertaalt die naar een advies, kandidaat en leesbare reden. Voorbeelden zijn `NEUTRAL`, `USE_PV_SURPLUS`, `SHIFT_FLEX_LOAD_NOW` en `DEFER_FLEX_LOAD`.

De score combineert forecastcontext met de werkelijke net- en apparaatstatus. Eén forecastsignaal schakelt dus nooit rechtstreeks een apparaat.

### Boilerlogica vanaf v1.3
De elektrische schakelstand `boilerOn` is niet langer voldoende om te bepalen of de boiler werkelijk een flexibele kandidaat is. De gevalideerde semantische status is leidend:

- `OP_TEMPERATUUR`: geen start- of uitstelkandidaat; de boiler is warm, ook wanneer de schakelaar nog aan staat;
- `AFKOELEN_WACHT`: geen kandidaat zolang de eindstatus nog wordt bevestigd;
- `VERWARMEN`: kan bij dure netimport als uitstelbare boilerbelasting worden herkend;
- `UIT`: kan, wanneer de overige M7-condities daarvoor aanleiding geven, als startkandidaat worden gebruikt;
- `AAN_WACHT` en `ONBEKEND`: conservatief geen boilerkandidaat.

De boilerstatus moet bovendien maximaal 25 minuten oud zijn. Is de publicatie ouder, dan gebruikt M7 de boiler uit veiligheid niet als kandidaat.

## Outputs
Per kwartier wordt een nieuw sample rechtstreeks toegevoegd aan `docs/data/m7-opportunity.json`. GitHub is daarmee de persistente historie voor de website; maximaal 672 kwartiersamples worden bewaard.

Per sample worden onder andere opgeslagen:
- Opportunity Score;
- advies;
- kandidaat;
- reden;
- gebruikte M7-signalen;
- werkelijke import/export en apparaatcontext;
- `boilerState`, tijdstip en leeftijd van de status;
- `boilerStateFresh`, `boilerCanStart` en `boilerCanDefer`.

## Homey API-belasting
Per kwartier gebruikt deze flow één gezamenlijke device-uitlezing en één gezamenlijke Logic-uitlezing. Daarnaast leest v1.3 één keer de meest recente Energy Manager-baseline uit GitHub om de semantische boilerstatus te gebruiken. De Logic-uitlezing levert de vier M7-contextwaarden en het GitHub-token.

## Aangestuurde apparaten
**Geen.** Volledig read-only/shadow.

## Validatie v1.3
Op 16 augustus 2026 is v1.3 direct na de succesvolle end-to-end boilercyclus getest. Het testsample las `OP_TEMPERATUUR` als actuele boilerstatus, met een statusleeftijd van 5 minuten. M7 zette daarom zowel `boilerCanStart` als `boilerCanDefer` op `false` en koos bij het advies `DEFER_FLEX_LOAD` terecht kandidaat `NONE` in plaats van de warme boiler.

## Status
v1.3 is actief. v1.2 is uitgeschakeld zodat maar één versie van deze flow actief publiceert. De resultaten worden rechtstreeks door de actieve flow naar de tab **Schaduw** gepubliceerd.

## Afhankelijkheden
M7 – Prijs & PV Forecast, Energy Manager PV – Shadow Mode v1.6.4 (of een opvolger die dezelfde boilerstatus publiceert), P1, Tesla/Easee, boiler, Quooker en `GH_Status_Token`.
