# M7 – Prijs & PV Forecast

**Status:** 🟡 Actief als read-only contextflow  
**Flow:** `M7 - Prijs en PV forecast context - read only`

De flow draait iedere 15 minuten en stuurt geen apparaten aan.

## Doel
M7 voegt voorspellende context toe aan de Energy Orchestrator. De flow bepaalt niet zelf welk apparaat moet schakelen, maar levert relatieve signalen over elektriciteitsprijs en verwachte PV-productie.

## Trigger
Iedere 15 minuten.

## Inputs
- Frank Energie prijscontext vanuit Homey Flow-kaarten.
- Homey PV-forecast.
- Tijdvenster voor de beste verwachte PV-uren.

## Logica
De implementatie gebruikt bewust relatieve signalen in plaats van arbitraire absolute grenzen:

| Signaal | Gedeelde Homey Logic-variabele | Betekenis |
| --- | --- | --- |
| `priceNegative` | `M7_Price_Negative` | De actuele elektriciteitsprijs is negatief. |
| `priceCheapNext4h` | `M7_Price_Cheap_Next4h` | Nu is relatief goedkoop ten opzichte van de komende vier uur. |
| `priceExpensiveNext4h` | `M7_Price_Expensive_Next4h` | Nu is relatief duur ten opzichte van de komende vier uur. |
| `pvTop4h` | `M7_PV_Top4h` | Het huidige uur behoort tot de vier beste verwachte PV-uren tussen 09:00 en 18:00. |

De eerder gebruikte vaste grens van 15 kWh per dag is verwijderd; deze had onvoldoende inhoudelijke betekenis voor de regeling.

## Outputs
De vier signalen worden nu opgeslagen als **gedeelde Homey Logic-booleans**. Dit vervangt de eerdere kaart-lokale `M7_CONTEXT`-state, omdat HomeyScript `get()/set()` niet betrouwbaar tussen verschillende scriptkaarten gedeeld wordt.

De bestaande zichtbare Flow-tags blijven daarnaast beschikbaar:

- `M7 Price Negative`
- `M7 Price Cheap Next4h`
- `M7 Price Expensive Next4h`
- `M7 PV Top4h 09-18`

## Aangestuurde apparaten
**Geen.** Deze flow is volledig read-only/contextvormend.

## Status
Actief als databron voor de parallelle `M7 - Opportunity Score - Shadow`-analyse.

## Afhankelijkheden
Frank Energie/Homey prijskaarten, Homey PV-forecast en de vier gedeelde M7 Logic-variabelen. De toekomstige Victron ESS-regeling kan deze context gebruiken, maar M7 bestuurt Victron niet rechtstreeks.
