# Lokale Homey → GitHub status-sync — HISTORISCH / NIET ACTIVEREN

De oude 15-minuten Homey→GitHub-statussync, `docs/data/homey-status.json` en het advies om `GH_Status_Token` in Homey Logic aan te maken zijn uitgefaseerd. Heractiveer deze flow of gedeelde GitHub-token **niet**. GitHub Pages toont alleen een neutrale pagina en is niet meer de EMS-databus.

Actuele status en geschiedenis komen uit de Homey→Pi-statepush en de private Pi-database/API. Zie [Homey–Pi dataflow](docs/architecture/homey-pi-runtime-dataflow.md), [Current EMS State](docs/architecture/CURRENT-EMS-STATE.md) en [publieke-data-grens](docs/architecture/public-data-boundary.md).

Dit document blijft uitsluitend bestaan als historisch migratiespoor.
