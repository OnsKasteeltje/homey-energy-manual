# Energy Core v2 — validity update v0.10.7

## Status

**Actieve Core:** `EM v2 | 00 Core Tick | v0.10.7 (SOURCE_SKEW warning)`  
**Control mode:** `SHADOW`  
**P1-rol:** autoritatieve bron voor netto import/export en flexbudget  
**PV-bronnen:** diagnostische/afgeleide huisbalans, met afzonderlijke freshness- en synchronisatiecontrole

## Aanleiding

Tot en met v0.10.6 werd de afgeleide huisbalans ongeldig zodra de timestamps van P1, SolarEdge en beide GoodWe-bronnen meer dan 180 seconden uit elkaar lagen. Dat bleek te streng: de PV-integraties leveren geldige waarden met een tragere updatecadans dan P1. Een normale GoodWe/SolarEdge-updatevertraging van enkele minuten leidde daardoor ten onrechte tot `SOURCE_SKEW` als harde balance failure.

## Nieuwe validity-semantiek

v0.10.7 scheidt **bron-freshness** van **bronsynchronisatie**.

- Alle vier timestamps moeten aanwezig zijn.
- De oudste bron mag maximaal 600 seconden oud zijn (`SOURCE_MAX_AGE_MS = 10 min`).
- P1 blijft apart maximaal 60 seconden oud voor `grid_measurement_valid` en flexbesluitvorming.
- Een onderlinge timestamp-skew groter dan 180 seconden maakt de bronnen **niet** langer automatisch ongeldig zolang alle bronnen nog binnen de 10-minuten freshness vallen.
- In dat geval wordt `SOURCE_SKEW_WARNING` gepubliceerd als diagnostische waarschuwing.
- Alleen ontbrekende of te oude P1/PV-bronnen geven `SOURCE_STALE_OR_MISSING` en blokkeren de afgeleide huis/PV-balans.
- Een fysiek inconsistente balans blijft onafhankelijk ongeldig via `NEGATIVE_HOUSE_BALANCE` of `KNOWN_LOADS_EXCEED_HOUSE`.

De kern is daarmee:

```text
source_fresh_valid = timestamps_present
                  && oldest_source_age <= 600 s

source_synchronized = timestamp_skew <= 180 s
source_skew_warning  = source_fresh_valid && !source_synchronized

derived_house_balance_valid = source_fresh_valid
                           && physical_balance_valid

grid_measurement_valid = p1_age <= 60 s
```

## Gepubliceerde diagnostiek

`balance.source_timing` bevat vanaf v0.10.7 expliciet:

```text
valid         = freshness-validity
fresh         = freshness-validity
synchronized  = skew <= 180 s
warning       = SOURCE_SKEW_WARNING | null
maxAgeSec
skewSec
sources.p1
sources.solarEdge
sources.goodWe4200
sources.goodWe2000
```

Hierdoor kan de website/operator onderscheid maken tussen:

1. **vers en gesynchroniseerd** — normale situatie;
2. **vers maar asynchroon** — bruikbare afgeleide balans met `SOURCE_SKEW_WARNING`;
3. **stale/missing** — afgeleide balans ongeldig;
4. **P1 stale** — flexbudget fail-closed, onafhankelijk van PV.

## End-to-end validatie — 21 augustus 2026

Na de cut-over is één Core-run en één Publisher-run uitgevoerd. De gepubliceerde revision `1088` bevestigde:

- `source_sample_at = 2026-08-21T11:13:23.276Z`;
- `balance.valid = true`;
- `balance.reason = OK`;
- `source_timing.valid = true`;
- `source_timing.fresh = true`;
- `source_timing.synchronized = false`;
- `source_timing.warning = SOURCE_SKEW_WARNING`;
- oudste bronleeftijd `545 s`, dus binnen de grens van `600 s`;
- timestamp-skew `536 s`, dus boven de synchronisatiegrens van `180 s`;
- P1-leeftijd `9 s`, dus `p1Fresh = true`;
- `grid_measurement_valid = true`;
- `derived_house_balance_valid = true`;
- `flex_budget_source = P1_NET_EXPORT`;
- `energy_budget.balance_reason = OK`.

De test bewijst precies het bedoelde gedrag: een normale PV-updateachterstand veroorzaakt nog wel zichtbare diagnostiek, maar **geen harde `SOURCE_SKEW` balance failure** zolang alle individuele bronnen voldoende vers zijn.

## Architectuurimpact

Er zijn geen extra device-reads, pollers of schedulers toegevoegd. Core blijft één fysieke Homey-snapshot per tick gebruiken. De Publisher blijft losgekoppeld en publiceert uitsluitend de reeds opgebouwde Logic-state. Daardoor verandert deze validity-correctie niets aan het Homey-loadbudget.

> Laatste update: **21 augustus 2026 — Core v0.10.7**. SOURCE_SKEW is voortaan een waarschuwing bij verse maar asynchrone PV-bronnen; alleen echte staleness/missing data blokkeert de afgeleide huisbalans. P1 blijft autoritatief voor flex.