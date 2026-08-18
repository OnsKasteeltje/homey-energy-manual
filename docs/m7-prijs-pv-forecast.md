# M7 – Prijs & PV Forecast

**Status:** 🟡 Actief als read-only contextflow  
**Huidige flow:** `M7 - Prijs en PV forecast context - read only`  
**Doelarchitectuur:** PBTH als optionele read-only prijscontext-provider voor Energy Core v2

De huidige contextflow draait iedere 15 minuten en stuurt geen apparaten aan. De doelarchitectuur houdt deze verantwoordelijkheid expliciet los van de beslislaag: de contextprovider verzamelt en normaliseert prijs- en forecastdata, Energy Core bepaalt wat ermee gebeurt.

## Doel
M7 voegt voorspellende context toe aan de Energy Orchestrator. De flow bepaalt niet zelf welk apparaat moet schakelen, maar levert relatieve en absolute signalen over elektriciteitsprijs en verwachte PV-productie.

## Huidige runtime

### Trigger
Iedere 15 minuten.

### Inputs
- Frank Energie prijscontext vanuit Homey Flow-kaarten.
- Homey PV-forecast.
- Tijdvenster voor de beste verwachte PV-uren.

### Logica
De huidige implementatie gebruikt bewust relatieve signalen:

| Signaal | Gedeelde Homey Logic-variabele | Betekenis |
| --- | --- | --- |
| `priceNegative` | `M7_Price_Negative` | De actuele elektriciteitsprijs is negatief. |
| `priceCheapNext4h` | `M7_Price_Cheap_Next4h` | Nu is relatief goedkoop ten opzichte van de komende vier uur. |
| `priceExpensiveNext4h` | `M7_Price_Expensive_Next4h` | Nu is relatief duur ten opzichte van de komende vier uur. |
| `pvTop4h` | `M7_PV_Top4h` | Het huidige uur behoort tot de vier beste verwachte PV-uren tussen 09:00 en 18:00. |

De eerder gebruikte vaste grens van 15 kWh per dag is verwijderd; deze had onvoldoende inhoudelijke betekenis voor de regeling.

### Outputs
De vier signalen worden opgeslagen als gedeelde Homey Logic-booleans. De bestaande zichtbare Flow-tags blijven daarnaast beschikbaar:

- `M7 Price Negative`
- `M7 Price Cheap Next4h`
- `M7 Price Expensive Next4h`
- `M7 PV Top4h 09-18`

### Aangestuurde apparaten
**Geen.** Deze contextlaag is volledig read-only.

---

# PBTH → Energy Core Context-contract v0.1

Power by the Hour (PBTH) wordt in de doelarchitectuur uitsluitend gebruikt als **prijscontext-provider**. PBTH krijgt geen beslis- of actuatorverantwoordelijkheid voor boiler, Tesla of Victron.

```text
PBTH
  ↓
PriceContextAdapter
  ↓
EM2_Context
  ↓
Energy Core v2
  ↓
WW Planner / Tesla Planner / later Victron
```

## Ontwerpprincipes

1. **Single responsibility** — PBTH levert prijzen; Energy Core neemt beslissingen.
2. **Read-only integratie** — geen PBTH-batterij-, EV- of load-control gebruiken binnen de Core-route.
3. **Geen extra device-scan** — prijscontext mag geen nieuwe periodieke `getDevices()` veroorzaken.
4. **Freshness expliciet** — stale of onvolledige prijsdata mag nooit opportunistische fysieke Control veroorzaken.
5. **Bron transparant** — iedere contextsnapshot publiceert bron, tijdstip en quality/freshness.
6. **Marginale kosten** — importprijs en exportwaarde blijven gescheiden; eigen PV wordt niet als financieel gratis behandeld.

## Genormaliseerd contextobject

Voorgesteld contract:

```json
{
  "schema": "EM2_PRICE_CONTEXT_V0.1",
  "source": "PBTH",
  "source_instance": "<PBTH device/instance>",
  "generated_at": "<ISO timestamp>",
  "source_updated_at": "<ISO timestamp>",
  "freshness_age_min": 0,
  "quality": "GOOD",
  "slot_minutes": 15,

  "current_price_eur_kwh": 0.1234,
  "current_export_eur_kwh": 0.1500,

  "night_min_price_eur_kwh": 0.1012,
  "night_min_price_at": "2026-08-19T03:00:00+02:00",

  "best_price_before_10_eur_kwh": 0.1012,
  "best_price_before_10_at": "2026-08-19T03:00:00+02:00",

  "price_negative": false,
  "price_slots_available": 44,
  "horizon_end": "2026-08-19T23:45:00+02:00"
}
```

## PBTH mapping

De adapter vertaalt PBTH-data naar het genormaliseerde contract. Energy Core mag geen PBTH-specifieke veldnamen kennen.

| Energy Core veld | PBTH-bron / afleiding | Opmerking |
| --- | --- | --- |
| `current_price_eur_kwh` | actuele importprijs van huidige slot | Inclusief de voor ons relevante prijscomponenten zoals PBTH geconfigureerd. |
| `current_export_eur_kwh` | actuele export-/terugleverprijs | Niet afleiden uit importprijs wanneer PBTH aparte exportprijs levert. |
| `night_min_price_eur_kwh` | minimum importprijs in nieuw kalenderdag-nachtvenster | Alleen slots vanaf 00:00 lokale tijd meenemen voor nieuw WW-dagdoel. |
| `night_min_price_at` | timestamp van minimum nachtprijs | Lokale timezone behouden. |
| `best_price_before_10_eur_kwh` | minimum importprijs vanaf 00:00 tot 10:00 | Inclusief huidige slot wanneer binnen venster. |
| `best_price_before_10_at` | timestamp van goedkoopste slot vóór 10:00 | Gebruikt door WW Planner v0.12. |
| `price_negative` | `current_price_eur_kwh < 0` | Sterke opportunity, maar guards blijven gelden. |
| `price_slots_available` | aantal geldige toekomstige slots | Quality-indicator. |
| `horizon_end` | einde laatste geldige slot | Moet minimaal relevante WW-horizon afdekken. |

## Vensterdefinities voor WW Planner v0.12

### Nachtvenster

Voor het nieuwe kalenderdagdoel:

```text
start = 00:00 lokale tijd
end   = 10:00 lokale tijd
```

`night_min_price` mag nooit uit de avond vóór middernacht komen. Een opwarming om 23:00 hoort nog bij de oude lokale kalenderdag en telt daarom niet als nieuwe-dagoptimalisatie.

### Beste prijs vóór 10:00

```text
best_price_before_10 = min(importprijs van alle geldige slots tussen 00:00 en 10:00)
```

Wanneer een slot al volledig verstreken is, wordt het niet meer meegenomen in een nieuwe beslissing.

## Exportwaarde

`current_export_eur_kwh` vertegenwoordigt de marginale opportunity cost van eigen PV die anders geëxporteerd zou worden.

Voor WW Planner:

```text
pv_marginal_cost = current_export_eur_kwh
night_marginal_cost = geselecteerde importprijs
```

Een goedkope nachtprijs kan dus economisch beter zijn dan latere eigen PV wanneer:

```text
night_price + minimum_margin < expected_export_value
```

De ontwerp-marge van WW Planner v0.12 blijft initieel **€0,05/kWh** om triviale prijsverschillen niet tot extra thermische cycli te laten leiden.

## Freshness en quality guards

Voorgestelde quality-status:

| Quality | Voorwaarde | Gebruik |
| --- | --- | --- |
| `GOOD` | actuele slot gevonden, relevante horizon compleet, bron recent | volledige economische SHADOW-beslissing toegestaan |
| `DEGRADED` | actuele prijs aanwezig maar horizon deels incompleet | huidige prijs bruikbaar; geen optimistische nachtvergelijking op ontbrekende slots |
| `STALE` | bronouderdom boven limiet | prijscontext negeren voor opportunity |
| `INVALID` | ongeldige prijs/timestamps/schema | volledig negeren |

Initiële freshness-limiet:

```text
GOOD/DEGRADED source age <= 35 min
STALE source age > 35 min
```

Dit sluit aan op de huidige Context-freshness van Energy Core v2.

## Horizon guard

Voor een economische beslissing vóór 10:00 moet minimaal bekend zijn:

```text
horizon_end >= vandaag/volgende dag 10:00 lokale tijd
```

Indien niet:

```text
price_horizon_complete = false
quality = DEGRADED
night_economic = false
```

Een negatieve actuele prijs mag als actuele sterke opportunity worden gemarkeerd wanneer de actuele slotdata zelf `GOOD` is, maar de planner moet expliciet vastleggen dat de volledige horizon niet beschikbaar was.

## Afgeleide plannerwaarden

De adapter of Context-laag mag onderstaande afgeleide waarden publiceren, maar de uiteindelijke beslissing blijft in Energy Core:

```text
expected_wait_cost_eur_kwh
night_advantage_eur_kwh
night_economic
price_horizon_complete
price_context_fresh
```

Voor eerste SHADOW-versie:

```text
expected_wait_cost = min(best_price_before_10, expected_pv_marginal_cost)
night_advantage = expected_wait_cost - candidate_night_price
night_economic = night_advantage >= 0.05
```

`expected_pv_marginal_cost` komt niet uit PBTH-prijsdata alleen; voorlopig gebruiken we daarvoor de relevante exportwaarde. Later kan een uitgebreidere forecast/allocator rekening houden met Tesla- en batterijconcurrentie.

## Fail-safe gedrag

Bij `STALE`, `INVALID` of ontbrekende horizon:

- geen `NIGHT_PRICE_RELEASE / SHOULD` op basis van onzekere prijsvergelijking;
- geen economische fysieke write;
- PV-release mag alleen op actuele fysieke flex-surplus-data worden gebaseerd;
- 10:00 `DEADLINE_RELEASE / MUST` blijft beschikbaar;
- catch-up/safety blijft altijd boven prijsoptimalisatie staan.

## PBTH solar forecast

PBTH solar forecast wordt **niet opgenomen in fase 1** van dit contract. Eerst gebruiken we PBTH uitsluitend voor prijsdata.

Later kan een apart `PVContextProvider`-contract worden toegevoegd en gedurende meerdere dagen worden vergeleken met werkelijk gemeten productie. Hierdoor voorkomen we dat één app tegelijk zowel prijs- als PV-onzekerheid introduceert in WW Planner v0.12.

## Validatieplan vóór gebruik in SHADOW

PBTH wordt pas als Core-contextbron gebruikt nadat minimaal onderstaande checks zijn uitgevoerd:

1. actuele PBTH-importprijs vergelijken met zichtbare/providerprijs;
2. exportprijs controleren tegen de geconfigureerde terugleverstructuur;
3. goedkoopste nacht-slot handmatig narekenen uit de ontvangen slots;
4. `best_price_before_10` handmatig narekenen;
5. lokale tijd/DST en 00:00-daggrens controleren;
6. freshness simuleren door oude context als `STALE` te classificeren;
7. onvolledige horizon als `DEGRADED` classificeren;
8. bevestigen dat geen PBTH-actuatorstrategie actief deelneemt aan boiler/Tesla/Victron-Control.

## Implementatiestappen

```text
Fase 0  documentatie/contract                  ← huidige status
Fase 1  PBTH prijsdata read-only observeren
Fase 2  genormaliseerde EM2 price context publiceren
Fase 3  enkele dagen prijs/context vergelijken
Fase 4  WW Planner v0.12 met PBTH in PURE SHADOW
Fase 5  pas na validatie economische Control overwegen
```

Tijdens fase 1–4 blijven fysieke boilerwrites vanuit deze nieuwe route uitgeschakeld.

## Status

De huidige runtime blijft voorlopig `EM v2 | 30 Context | Price + PV v0.1` gebruiken. Het PBTH-contract hierboven is **doelontwerp** en is nog niet actief in Homey.

> **Volgende stap:** vaststellen of PBTH op de Homey aanwezig/geconfigureerd is en, indien gewenst, één minimale read-only proef doen om de daadwerkelijk beschikbare prijsvelden/slots te inventariseren. Geen actuatie en geen wijziging van bestaande Core-routes tijdens die proef.
