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

<script>
(function () {
  const BASELINE_URL = "https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/shadow-baseline-v01.json";

  async function patchEnergyManagerCard() {
    try {
      const u = new URL(BASELINE_URL);
      u.searchParams.set("_", Date.now());
      const response = await fetch(u, { cache: "no-store" });
      if (!response.ok) return;
      const baseline = await response.json();
      if (!baseline || !baseline.source) return;

      const cards = Array.from(document.querySelectorAll("#homey-flow-dashboard .flow-card"));
      const card = cards.find(c => {
        const title = c.querySelector(".flow-card-title");
        return title && title.textContent.trim() === "Energie Manager PV - Shadow Mode";
      });
      if (!card) return;

      const link = card.querySelector(".flow-title-link");
      const title = card.querySelector(".flow-card-title");
      if (link) link.textContent = baseline.source;
      else if (title) title.textContent = baseline.source;

      card.classList.remove("status-off", "status-error", "status-shadow", "status-unknown");
      card.classList.add(baseline.enabled ? "status-active" : "status-off");

      const pill = card.querySelector(".status-pill");
      if (pill) {
        pill.className = `status-pill ${baseline.enabled ? "status-active" : "status-off"}`;
        pill.textContent = baseline.enabled ? "● Actief" : "● Uit";
      }

      const enabled = card.querySelector(".flow-meta span:first-child strong");
      if (enabled) enabled.textContent = baseline.enabled ? "ja" : "nee";

      const detail = card.querySelector(".flow-detail");
      if (detail) detail.textContent = "Actuele operationele Energy Manager · shadow/read-only · status uit baseline-publicatie";
    } catch (_) {
      // Bij een tijdelijke fout blijft de reguliere homey-statusweergave staan.
    }
  }

  function schedulePatch() {
    window.setTimeout(patchEnergyManagerCard, 500);
    window.setTimeout(patchEnergyManagerCard, 1500);
  }

  document.addEventListener("DOMContentLoaded", schedulePatch);
  document.addEventListener("DOMContentSwitch", schedulePatch);
})();
</script>

## Energieprioriteit

```text
huishoudelijk verbruik → Tesla → boiler → teruglevering
```

De centrale Energie Manager draait momenteel in **shadow mode**. De algemene status hierboven komt uit `docs/data/homey-status.json`. Voor de **actuele Energy Manager-versie en enabled-status** gebruikt de homepage aanvullend `docs/data/shadow-baseline-v01.json`, zodat een oude uitgeschakelde flowversie niet als hoofdstatus wordt getoond.

## Betekenis van de statussen

<div class="legend">
  <span class="status-pill status-active">● Actief</span>
  <span class="status-pill status-shadow">● Shadow/Test</span>
  <span class="status-pill status-off">● Uit</span>
  <span class="status-pill status-error">● Fout</span>
</div>

## Documentatie

Gebruik de navigatie voor de functionele beschrijving, variabelen, architectuur en wijzigingshistorie.
