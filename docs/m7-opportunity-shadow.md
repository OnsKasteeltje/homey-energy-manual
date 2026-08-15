# M7 – Opportunity Score Shadow

**Status:** 🟡 Actief in shadow mode  
**Flow:** `M7 - Opportunity Score - Shadow`

De flow draait iedere 15 minuten en stuurt geen apparaten aan.

## Doel
Deze flow onderzoekt onafhankelijk of prijs- en PV-forecastinformatie daadwerkelijk extra waarde toevoegt aan de bestaande Energy Manager. Hij draait parallel aan de baseline/shadowflow en verandert die dataset niet.

## Trigger
Iedere 15 minuten.

## Inputs
- vier gedeelde Homey Logic-booleans uit M7 Prijs & PV Forecast;
- P1/netpositie;
- Tesla/Easee-status en laadvermogen;
- boilerstatus en boilervermogen;
- Quookerstatus.

De vier contextvariabelen zijn `M7_Price_Negative`, `M7_Price_Cheap_Next4h`, `M7_Price_Expensive_Next4h` en `M7_PV_Top4h`.

## Logica
De flow berekent een **Opportunity Score** en vertaalt die naar een advies, kandidaat en leesbare reden. Voorbeelden zijn `NEUTRAL`, `USE_PV_SURPLUS`, `SHIFT_FLEX_LOAD_NOW` en `DEFER_FLEX_LOAD`.

De score combineert forecastcontext met de werkelijke net- en apparaatstatus. Eén forecastsignaal schakelt dus nooit rechtstreeks een apparaat.

## Outputs
Per kwartier wordt een nieuw sample rechtstreeks toegevoegd aan `docs/data/m7-opportunity.json`. GitHub is daarmee de persistente historie voor de website; maximaal 672 kwartiersamples worden bewaard.

Per sample worden onder andere opgeslagen:
- Opportunity Score;
- advies;
- kandidaat;
- reden;
- gebruikte M7-signalen;
- werkelijke import/export en apparaatcontext.

## Homey API-belasting
Per kwartier gebruikt deze flow één gezamenlijke device-uitlezing en één gezamenlijke Logic-uitlezing. De Logic-uitlezing levert de vier M7-contextwaarden en het GitHub-token.

## Aangestuurde apparaten
**Geen.** Volledig read-only/shadow.

## Status
Actief. De resultaten worden rechtstreeks door deze flow naar de tab **Schaduw** gepubliceerd. De directe GitHub-writer is op 15 augustus 2026 succesvol gevalideerd met het eerste echte M7-sample.

## Afhankelijkheden
M7 – Prijs & PV Forecast, P1, Tesla/Easee, boiler, Quooker en `GH_Status_Token`.
