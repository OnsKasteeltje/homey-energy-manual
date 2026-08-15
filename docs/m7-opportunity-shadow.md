# M7 – Opportunity Score Shadow

**Status:** 🟡 Actief in shadow mode  
**Flow:** `M7 - Opportunity Score - Shadow`

De flow draait iedere 15 minuten en stuurt geen apparaten aan.

## Doel
Deze flow onderzoekt onafhankelijk of prijs- en PV-forecastinformatie daadwerkelijk extra waarde toevoegt aan de bestaande Energy Manager. Hij draait parallel aan de baseline/shadowflow en verandert die dataset niet.

## Trigger
Iedere 15 minuten.

## Inputs
- `M7_CONTEXT` met prijs- en PV-signalen.
- P1/netpositie.
- Werkelijke PV-/overschotcontext.
- Tesla/Easee-status.
- Boilerstatus.
- Quookerstatus/context waar beschikbaar.
- Tijdstip en relevante bedrijfsvensters.

## Logica
De flow berekent een **Opportunity Score** en vertaalt die naar een advies, kandidaat en leesbare reden. Voorbeelden zijn `NEUTRAL`, `USE_PV_SURPLUS`, `SHIFT_FLEX_LOAD_NOW` en `DEFER_FLEX_LOAD`.

Het doel is niet dat één M7-signaal direct een apparaat schakelt. De score combineert forecastcontext met wat er werkelijk op het net en bij de flexibele belastingen gebeurt.

## Outputs
Per kwartier worden onder andere opgeslagen:
- Opportunity Score;
- advies;
- kandidaat;
- reden;
- gebruikte M7-signalen;
- werkelijke import/export en apparaatcontext.

De historie wordt apart bewaard in `M7_SHADOW_ANALYSIS` en is bedoeld voor vergelijking met de reguliere shadowdata.

## Aangestuurde apparaten
**Geen.** Volledig read-only/shadow.

## Status
Actief. De resultaten worden op de tab **Schaduw** zichtbaar gemaakt zodra de dedicated GitHub shadow-sync actuele data publiceert.

## Afhankelijkheden
M7 – Prijs & PV Forecast, P1 en de uitleesbare Homey-apparaatstatussen.
