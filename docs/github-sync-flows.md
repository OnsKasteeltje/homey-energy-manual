# GitHub status- en shadow-sync

**Status:** 🟢 Reguliere status-sync actief; centrale shadow-sync uitgeschakeld  
**Flows:** `GitHub status sync - Homey lokaal` en `GitHub shadow sync - Homey lokaal`

De reguliere status-sync blijft periodiek actief. De aparte `GitHub shadow sync - Homey lokaal` staat nu **uit**, omdat shadowdata voortaan door de flows die de state zelf bezitten rechtstreeks wordt gepubliceerd. Geen van deze synchronisaties stuurt apparaten aan.

## Doel
De website ontvangt geselecteerde Homey-status- en shadowinformatie via uitgaande GitHub-writes. Er is geen inkomende verbinding naar Homey nodig.

## Reguliere status-sync
`GitHub status sync - Homey lokaal` publiceert de algemene flowstatus naar:

- `docs/data/homey-status.json`

Dit bestand voedt de flowkaarten en de live synchronisatietijd op de homepage.

## Shadowpublicatie — state-eigenaarprincipe
HomeyScript `get()/set()`-state blijkt lokaal aan de betreffende scriptkaart gekoppeld. Daarom kan een centrale syncscript die state niet betrouwbaar uitlezen.

De architectuur is daarom aangepast:

| State-eigenaar | Publicatiebestand | Ritme |
| --- | --- | --- |
| `Energie Manager PV - Shadow Mode` | `docs/data/shadow-baseline-v01.json` | circa iedere 15 minuten |
| `Energie Manager PV - Shadow Mode v0.2 Quooker` | `docs/data/shadow-v02-quooker.json` | circa iedere 15 minuten wanneer actief |
| `M7 - Opportunity Score - Shadow` | `docs/data/m7-opportunity.json` | iedere 15 minuten |

De **zelfde HomeyScript-kaart die de lokale state opbouwt** publiceert dus ook die state. Daardoor is geen kaart-overstijgende HomeyScript-state nodig.

## Foutisolatie
GitHub-publicatie staat in een `try/catch`. Als GitHub tijdelijk niet bereikbaar is, blijft de shadowflow gewoon meten en lokaal samples bewaren. Een websiteprobleem mag de energiemeting dus niet stoppen.

## Homey API-belasting
De baseline- en v0.2-flows halen het GitHub-token alleen op wanneer een publicatie nodig is, ongeveer eens per kwartier. M7 gebruikt één gezamenlijke Logic-uitlezing per kwartier voor zowel de contextvariabelen als het token.

De voormalige centrale `GitHub shadow sync - Homey lokaal` staat uit en veroorzaakt daardoor geen periodieke extra Homey-calls meer.

## Aangestuurde apparaten
**Geen.** Dit is uitsluitend publicatie/telemetrie.

## Afhankelijkheden
HomeyScript, `GH_Status_Token` en de repository `OnsKasteeltje/homey-energy-manual`.
