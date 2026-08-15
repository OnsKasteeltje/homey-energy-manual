
(function () {
  const LIVE_STATUS_URL =
    "https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/homey-status.json";

  const statusLabels = {
    active: "Actief",
    shadow: "Shadow/Test",
    off: "Uit",
    error: "Fout",
    unknown: "Onbekend"
  };

  const statusClass = (s) =>
    ["active", "shadow", "off", "error"].includes(s) ? `status-${s}` : "status-unknown";

  // Koppeling tussen Homey-flows op de hoofdpagina en hun functionele documentatie.
  // Nieuwe flows krijgen voortaan bij voorkeur meteen een documentatielink.
  const flowDocs = {
    "Warm water optimalisatie - PV boiler + CV advies": "warm-water/",
    "Energie Manager PV - Shadow Mode": "energie-manager/",
    "Energie Manager PV - Shadow Mode v0.2 Quooker": "energie-manager/",
    "M7 - Prijs en PV forecast context - read only": "m7-prijs-pv-forecast/",
    "M7 - Opportunity Score - Shadow": "m7-opportunity-shadow/",
    "Energie Manager - omschakeling v0.2 - 16 aug 00:00": "energie-manager/",
    "GitHub status sync - Homey lokaal": "github-sync-flows/"
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  async function fetchJson(url) {
    const u = new URL(url, document.baseURI);
    u.searchParams.set("_", Date.now());
    const response = await fetch(u, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async function loadStatus() {
    const dashboard = document.getElementById("homey-flow-dashboard");
    const update = document.getElementById("homey-last-update");
    const health = document.getElementById("homey-sync-health");
    if (!dashboard) return;

    let data;
    try {
      try {
        data = await fetchJson(LIVE_STATUS_URL);
      } catch (_) {
        data = await fetchJson("data/homey-status.json");
      }

      dashboard.innerHTML = "";
      for (const flow of (data.flows || [])) {
        const status = flow.status || (flow.broken ? "error" : flow.enabled ? "active" : "off");
        const card = document.createElement("article");
        card.className = `flow-card ${statusClass(status)}`;
        const docPath = flowDocs[flow.name];
        const title = docPath
          ? `<a href="${escapeHtml(docPath)}" title="Open flowbeschrijving">${escapeHtml(flow.name)}</a>`
          : escapeHtml(flow.name);
        const docLink = docPath
          ? `<div class="flow-doc-link"><a href="${escapeHtml(docPath)}">Bekijk flowbeschrijving →</a></div>`
          : "";
        card.innerHTML = `
          <div class="flow-card-header">
            <div>
              <div class="flow-category">${escapeHtml(flow.category || "Flow")}</div>
              <div class="flow-card-title">${title}</div>
            </div>
            <span class="status-pill ${statusClass(status)}">● ${escapeHtml(statusLabels[status] || statusLabels.unknown)}</span>
          </div>
          <div class="flow-detail">${escapeHtml(flow.detail || "")}</div>
          <div class="flow-meta">
            <span>Enabled: <strong>${flow.enabled ? "ja" : "nee"}</strong></span>
            <span>Broken: <strong>${flow.broken ? "ja" : "nee"}</strong></span>
          </div>
          ${docLink}
        `;
        dashboard.appendChild(card);
      }

      const dt = data.generated_at ? new Date(data.generated_at) : null;
      update.textContent = dt && !Number.isNaN(dt.getTime())
        ? `Laatst gesynchroniseerd: ${dt.toLocaleString("nl-NL")} · bron: ${data.source || "Homey"}`
        : "Synchronisatietijd onbekend";

      if (data.sync_ok === false) {
        health.className = "health-badge health-error";
        health.textContent = "● synchronisatiefout";
      } else {
        health.className = "health-badge health-ok";
        health.textContent = "● synchronisatie OK";
      }
    } catch (error) {
      dashboard.innerHTML = `
        <article class="flow-card status-error">
          <div class="flow-card-title">Homey-status kon niet worden geladen</div>
          <div class="flow-detail">${escapeHtml(error.message)}</div>
        </article>`;
      update.textContent = "Geen actuele synchronisatie beschikbaar";
      health.className = "health-badge health-error";
      health.textContent = "● synchronisatiefout";
    }
  }

  document.addEventListener("DOMContentLoaded", loadStatus);
  document.addEventListener("DOMContentSwitch", loadStatus);
})();
