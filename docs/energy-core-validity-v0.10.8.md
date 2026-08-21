# Energy Core v2 — validity update v0.10.8

## Status

**Actieve Core:** `EM v2 | 00 Core Tick | v0.10.8 (source-specific freshness)`  
**Control mode:** `SHADOW`  
**P1-rol:** autoritatieve bron voor netto import/export en flexbudget  
**PV-bronnen:** bron-specifieke freshness voor de afgeleide huisbalans

## Aanleiding

v0.10.7 maakte `SOURCE_SKEW` terecht diagnostisch zolang PV-bronnen vers waren, maar gebruikte nog één gezamenlijke freshness-grens van 10 minuten. Dat bleek niet passend bij de SolarEdge-cloudintegratie. De gebruikte Homey Solar Panels-integratie adviseert voor SolarEdge geen interval lager dan 15 minuten vanwege de SolarEdge API-limiet. Daardoor kon een normale SolarEdge-updatecadans ten onrechte `SOURCE_STALE_OR_MISSING` veroorzaken.

## Nieuwe validity-semantiek

v0.10.8 gebruikt bron-specifieke freshness-SLA's:

- P1: maximaal 60 seconden voor `grid_measurement_valid` en flexbesluitvorming;
- SolarEdge cloud: maximaal 20 minuten, zodat de normale 10–15 minuten API-cadans plus beperkte jitter wordt geaccepteerd;
- GoodWe 4,2 kW: maximaal 10 minuten;
- GoodWe 2 kW: maximaal 10 minuten;
- timestamp-skew >180 seconden blijft `SOURCE_SKEW_WARNING` zolang alle PV-bronnen binnen hun eigen freshness-SLA vallen;
- alleen een bron buiten zijn eigen SLA of een ontbrekende timestamp geeft `SOURCE_STALE_OR_MISSING` voor de afgeleide huisbalans;
- P1 blijft onafhankelijk autoritatief voor het flex-exportbudget.

```text
solarEdgeFresh = solarEdgeAge <= 1200 s
goodWe42Fresh  = goodWe42Age  <= 600 s
goodWe20Fresh  = goodWe20Age  <= 600 s

source_fresh_valid = timestamps_present
                  && solarEdgeFresh
                  && goodWe42Fresh
                  && goodWe20Fresh

source_synchronized = timestamp_skew <= 180 s
source_skew_warning  = source_fresh_valid && !source_synchronized

derived_house_balance_valid = source_fresh_valid
                           && physical_balance_valid

grid_measurement_valid = p1_age <= 60 s
```

## Gepubliceerde diagnostiek

`balance.source_timing.freshness` bevat vanaf v0.10.8 per PV-bron:

```text
solarEdge.fresh / ageSec / maxAgeSec
goodWe4200.fresh / ageSec / maxAgeSec
goodWe2000.fresh / ageSec / maxAgeSec
```

Daarmee is zichtbaar welke bron eventueel werkelijk stale is, zonder alle PV-bronnen aan dezelfde updatecadans te koppelen.

## End-to-end validatie — 21 augustus 2026

Na de cut-over is Core v0.10.8 handmatig uitgevoerd en direct via Publisher v1.0.3 gepubliceerd als revision `1094`.

Resultaat:

- `source_sample_at = 2026-08-21T11:34:10.534Z`;
- `generated_at = 2026-08-21T11:34:15.820Z`;
- `balance.valid = true`;
- `balance.reason = OK`;
- `source_timing.valid = true`;
- `source_timing.synchronized = false`;
- `source_timing.warning = SOURCE_SKEW_WARNING`;
- SolarEdge leeftijd `893 s` bij toegestane `1200 s` → `fresh = true`;
- GoodWe 4,2 kW leeftijd `259 s` bij toegestane `600 s` → `fresh = true`;
- GoodWe 2 kW leeftijd `259 s` bij toegestane `600 s` → `fresh = true`;
- P1 leeftijd `4 s` → `p1Fresh = true`;
- `derived_house_balance_valid = true`;
- `flex_budget_source = P1_NET_EXPORT`.

Deze validatie bewijst dat een normale SolarEdge-cloudcadans niet langer als echte staleness wordt behandeld. SOURCE_SKEW blijft zichtbaar als diagnostische waarschuwing, terwijl P1 de autoritatieve basis voor flexbesluitvorming blijft.

## Architectuurimpact

Er zijn geen extra SolarEdge-polls, device-reads of schedulers toegevoegd. Dit voorkomt extra Homey/API-belasting. De oplossing past de validity-semantiek aan de feitelijke bron-SLA aan in plaats van de bron agressiever te pollen.

> Laatste update: **21 augustus 2026 — Core v0.10.8**.