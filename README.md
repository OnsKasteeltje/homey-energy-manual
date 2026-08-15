# Homey Energy Manual

## GitHub Pages

De echte GitHub Actions workflow staat in:

`.github/workflows/pages.yml`

Let op: op macOS zijn mappen die met een punt beginnen standaard verborgen.
Druk in Finder op **Cmd + Shift + .** om verborgen bestanden te tonen.

Er staat ook een zichtbare kopie in de hoofdmap:
`pages-workflow-reference.yml`

Die zichtbare kopie is alleen ter controle; GitHub Actions gebruikt uitsluitend het bestand in `.github/workflows/`.



## Dynamische status

De actuele Flow-status wordt lokaal door Homey iedere 15 minuten naar
`docs/data/homey-status.json` geschreven.

Zie `LOCAL_STATUS_SETUP.md`.

De oude GitHub→Homey polling-workflow is verwijderd.
