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
Per kwartier worden onder andere opgeslagen:

- Opportunity Score;
- advies;
- kandidaat;
- reden;
- gebruikte M7-signalen;
- werkelijke import/export en apparaatcontext.

De historie blijft kaart-lokaal bewaard in `M7_SHADOW_ANALYSIS` met maximaal 672 kwartiersamples. **Dezelfde scriptkaart die deze state bezit publiceert de dataset ook rechtstreeks naar GitHub** als `docs/data/m7-opportunity.json`. Hierdoor hoeft een aparte syncscript de lokale state niet meer te proberen uitlezen.

GitHub-publicatiefouten worden afgevangen en stoppen de shadowanalyse niet.

## Homey API-belasting
Per kwartier gebruikt deze flow één gezamenlijke device-uitlezing en één gezamenlijke Logic-uitlezing. Die Logic-uitlezing levert zowel de vier M7-contextwaarden als het GitHub-token voor publicatie.

## Aangestuurde apparaten
**Geen.** Volledig read-only/shadow.

## Status
Actief. De resultaten worden rechtstreeks door deze flow naar de tab **Schaduw** gepubliceerd.

## Afhankelijkheden
M7 – Prijs & PV Forecast, P1, Tesla/Easee, boiler, Quooker en `GH_Status_Token`.
