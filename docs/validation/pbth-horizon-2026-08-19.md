# PBTH DAP15 horizonvalidatie — 19 augustus 2026

## Status

De blokkade in `EM v2 | 30 Context | Price + PV v0.5` is geïsoleerd en opgelost in PURE SHADOW. Er zijn tijdens deze validatie geen fysieke boiler-, Tesla-, Quatt- of andere actuatorwrites uitgevoerd.

Productiestatus na de test:

- `EM v2 | 30 Context | Price + PV v0.4`: actief, `broken=false`.
- `EM v2 | 30 Context | Price + PV v0.5`: uitgeschakeld, `broken=false`.
- tijdelijke PBTH-horizonprobe: uitgeschakeld.

## Root cause

PBTH `prices_json(next_hours)` werkte zelf correct, maar de kaart-lokale Flow-token werd in de via de connector opgebouwde Advanced Flow met de verkeerde interne referentie aangesproken.

Niet werkend:

```text
homey:advancedflow:<card-id>::prices
```

Werkend voor een token uit een Advanced Flow action card:

```text
action::<card-id>::prices
```

Voor tekstvelden wordt de token vervolgens geïnterpoleerd als:

```text
[[action::<card-id>::prices]]
```

Met de gecorrigeerde notatie slaagden zowel een pure stringtest als native JSON-indexselectie op index 0.

## Exact gemeten horizon

De gecorrigeerde read-only probe ontving:

- 48 geldige DAP15-slots;
- 15 minuten per slot;
- nominaal 12,0 uur aan slots;
- resterende horizon op het eerste meetmoment: 11,849 uur;
- horizon-einde: 2026-08-19T22:00:00.000Z.

Een aansluitende PURE-SHADOW-run van v0.5 gaf:

```text
TEMP_PBTH_V05_OK_N48_H11p833_INTRADAY_C10_N
```

Daaruit volgt voor die run:

- 48 valide aaneengesloten slots;
- exacte resterende horizon 11,833 uur;
- `quality=GOOD` (vereist voor de gerapporteerde `INTRADAY`-modus);
- optimalisatiemodus `INTRADAY` omdat de resterende horizon op het runmoment net onder 12 uur lag;
- geen dekking tot morgen 10:00 (`coversTomorrow10=false`), dus nachtvoorverwarming blijft horizonmatig geblokkeerd.

## v0.5-correctie

De bufferkaart in v0.5 gebruikt nu rechtstreeks:

```text
value = [[action::aaaaaaaa-5001-4000-8000-aaaaaaaaaaaa::prices]]
```

De foutieve `droptoken=homey:advancedflow:...`-constructie is verwijderd. De rest van de v0.5-horizon- en veiligheidslogica is niet verruimd.

## Veiligheidsbesluit

v0.5 is na de succesvolle eenmalige shadow-validatierun weer uitgeschakeld. v0.4 blijft productie totdat freshness/revision-alignment en de gewenste cut-over afzonderlijk zijn bevestigd. Geen ontbrekende horizonwaarden worden afgeleid of verzonnen.
