# Homey EMS Core — source authority en rollback

## Huidige runtime (gecontroleerd 2026-10-13)

- Homey Advanced Flow: `227f8d3b-7551-46dd-837d-1b8c69add824`.
- Actief, `enabled=true`, `broken=false`: **Core V0.11p** (pinned source).
- Repositoryversie: `src/homey/core/core-v0.11p.candidate-homey.js` (oorspronkelijke bestandsnaam uit staging).
- **2026-10-14:** bestaande cron-trigger gewijzigd van 5 naar **2 minuten**
  als Live-freshnessproef. De actieve 59.064-teken HomeyScript-bron is
  vooraf byte-exact met de repository vergeleken. De post-update readback
  bevestigde: alleen `args.n` (5→2) gewijzigd, bestaande scripts, kaarten en
  verbindingen gelijk, `enabled=true`, `broken=false`. De 5-minuten
  rollback is dezelfde trigger terugzetten, niet de rollback-Core activeren.
  Nieuwe Pi-snapshotfrequentie is nog niet als runtimebewijs gemeten.
- Uitgeschakelde, behouden rollback-flow: **Core V0.11n**, met `core-v0.11n.live-homey.js` als historische source.
- Productie-Core is een observer/publisher; de Homey EV/WW-actuators blijven afzonderlijke fysieke control owners.

## Archivering van oude bronversies (2026-10-13)

De historische Core-code V0.11f, V0.11i, V0.11j, V0.11l, V0.11m en de tussentijdse V0.11o-candidate is uit de actuele GitHub-tree verwijderd. Het gaat niet om actieve Homey-flows. Deze volledige bestanden blijven herstelbaar via de Git-geschiedenis vóór de cleanup-commit. Er is geen alternatieve Core-flow geïnstalleerd of geactiveerd.

De documenten over eerdere live baselines, waaronder `docs/architecture/homey-runtime-baseline-2026-09-04.md`, zijn historische observaties en beschrijven geen actuele productieversie.

## Wijzigingsregel

Pas de bestaande productieflow pas aan na volledige live-HomeyScript-readback, vergelijking met de repositorybron en een gerichte regressietest. Behoud de bestaande rollback-flow en voer geen tweede Core-writer of Core-trigger in.

Bij een Core-wijziging altijd de actuele Homey-flow lezen; bouw de volledige productiecode nooit terug op vanuit oudere patches.
