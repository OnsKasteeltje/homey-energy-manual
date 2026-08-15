# Homey Energy Dashboard

<div class="status-toolbar">
  <div>
    <strong>Live status</strong><br>
    <span id="homey-last-update" class="muted">Status wordt geladen…</span>
  </div>
  <div id="homey-sync-health" class="health-badge health-unknown">● onbekend</div>
</div>

<div id="homey-flow-dashboard" class="flow-grid">
  <div class="flow-card loading-card">
    <div class="flow-card-title">Homey-status laden…</div>
  </div>
</div>

## Energieprioriteit

```text
huishoudelijk verbruik → Tesla → boiler → teruglevering
```

De centrale Energie Manager draait momenteel in **shadow mode**. De actuele status hierboven komt uit `docs/data/homey-status.json`, dat periodiek door GitHub Actions kan worden vernieuwd.

## Betekenis van de statussen

<div class="legend">
  <span class="status-pill status-active">● Actief</span>
  <span class="status-pill status-shadow">● Shadow/Test</span>
  <span class="status-pill status-off">● Uit</span>
  <span class="status-pill status-error">● Fout</span>
</div>

## Documentatie

Gebruik de navigatie voor de functionele beschrijving, variabelen, architectuur en wijzigingshistorie.
