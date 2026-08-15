# Lokale status-sync

**Flow:** `GitHub status sync - Homey lokaal`  
**Status:** configuratie — nog uitgeschakeld

De statuswebsite wordt niet door GitHub uit Homey opgehaald. Homey leest de relevante Flow-status lokaal en publiceert iedere 15 minuten alleen `homey-status.json` naar GitHub.

## Waarom deze richting?

- geen inbound toegang tot Homey;
- geen port forwarding;
- geen Homey API-token in GitHub Actions;
- de website krijgt alleen niet-geheime statusdata.

## Beveiliging

De GitHub fine-grained PAT wordt lokaal opgeslagen als Homey Logic tekstvariabele `GH_Status_Token`. De PAT wordt beperkt tot één repository met uitsluitend `Contents: Read and write`.

## Publicatiepad

`docs/data/homey-status.json`

De homepage leest dit bestand rechtstreeks uit de `main` branch.
