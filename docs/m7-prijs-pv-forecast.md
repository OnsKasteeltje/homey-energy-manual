# M7 – Prijs & PV Forecast

**Status:** 🟡 Actief als read-only contextflow  
**Flow:** `M7 - Prijs en PV forecast context - read only`

De flow draait iedere 15 minuten en stuurt geen apparaten aan.

## Doel
M7 voegt voorspellende context toe aan de Energy Orchestrator. De flow bepaalt niet zelf welk apparaat moet schakelen, maar levert relatieve signalen over elektriciteitsprijs en verwachte PV-productie.

## Trigger
De context wordt periodiek bijgewerkt op een kwartierbasis.

## Inputs
- Frank Energie prijscontext vanuit Homey Flow-kaarten.
- Homey PV-forecast.
- Tijdvenster voor de beste verwachte PV-uren.

## Logica
De huidige implementatie gebruikt bewust relatieve signalen in plaats van arbitraire absolute grenzen:

| Signaal | Betekenis |
| --- | --- |
| `priceNegative` | De actuele elektriciteitsprijs is negatief. |
| `priceCheapNext4h` | Nu is relatief goedkoop ten opzichte van de komende vier uur. |
| `priceExpensiveNext4h` | Nu is relatief duur ten opzichte van de komende vier uur. |
| `pvTop4h` | Het huidige uur behoort tot de vier beste verwachte PV-uren tussen 09:00 en 18:00. |

De eerder gebruikte vaste grens van 15 kWh per dag is verwijderd; deze had onvoldoende inhoudelijke betekenis voor de regeling.

## Outputs
De vier signalen worden als M7-context beschikbaar gemaakt voor verdere analyse en opgeslagen in `M7_CONTEXT`.

## Aangestuurde apparaten
**Geen.** Deze flow is read-only/contextvormend.

## Status
Actief als databron voor de parallelle M7 Opportunity Shadow-analyse.

## Afhankelijkheden
Frank Energie/Homey prijskaarten en Homey PV-forecast. De toekomstige Victron ESS-regeling kan deze context gebruiken, maar M7 bestuurt Victron niet rechtstreeks.
