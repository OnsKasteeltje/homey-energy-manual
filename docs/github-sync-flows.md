# GitHub status- en shadow-sync

**Status:** 🟡 Deels actief / shadow-sync nog in validatie  
**Flows:** `GitHub status sync - Homey lokaal` en `GitHub shadow sync - Homey lokaal`

De reguliere status-sync draait periodiek; de dedicated shadow-sync is ingesteld op iedere 15 minuten. Geen van beide stuurt apparaten aan.

## Doel
Deze flows publiceren alleen geselecteerde Homey-statusinformatie naar de documentatiesite. De website hoeft daardoor geen inkomende verbinding met Homey te maken.

## Trigger
- Reguliere status-sync: periodiek vanuit Homey.
- Dedicated shadow-sync: iedere 15 minuten.

## Inputs
### Status-sync
Geselecteerde live Homey-statussen die voor de website nodig zijn.

### Shadow-sync
- baseline shadowstate;
- Shadow v0.2 + Quooker-state;
- `M7_CONTEXT`;
- `M7_SHADOW_ANALYSIS`.

## Logica
Homey bouwt een beperkte JSON-payload en schrijft die uitgaand naar de GitHub-repository. Voor shadowmonitoring is bewust een aparte writer voorzien, zodat een probleem in de algemene status-sync de shadowpublicatie niet hoeft te blokkeren.

## Outputs
- `docs/data/homey-status.json`
- `docs/data/shadow-status.json`

De Schaduw-pagina leest de shadow-JSON rechtstreeks uit de repository, zodat iedere kwartierupdate geen volledige GitHub Pages-build nodig heeft.

## Aangestuurde apparaten
**Geen.** Dit is uitsluitend publicatie/telemetrie.

## Status
De website en het bootstrapbestand voor `shadow-status.json` zijn aanwezig. De dedicated Homey shadow-writer wordt nog gevalideerd; zolang die nog niet succesvol schrijft, toont de Schaduw-tab 0 samples.

## Afhankelijkheden
HomeyScript, een GitHub-token in Homey en de repository `OnsKasteeltje/homey-energy-manual`.
