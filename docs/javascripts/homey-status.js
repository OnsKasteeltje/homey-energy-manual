
(function () {
  const statusLabels = {
    active: "Actief",
    shadow: "Shadow/Test",
    off: "Uit",
    error: "Fout",
    unknown: "Onbekend"
  };

  const statusClass = (s) => {
    if (["active", "shadow", "off", "error"].includes(s)) return `status-${s}`;
    return "status-unknown";
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  async function loadStatus() {
    const dashboard = document.getElementById("homey-flow-dashboard");
    const update = document.getElementById("homey-last-update");
    const health = document.getElementById("homey-sync-health");
    if (!dashboard) return;

    try {
      const url = new URL("data/homey-status.json", document.baseURI);
      url.searchParams.set("_", Date.now());
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();

      dashboard.innerHTML = "";
      for (const flow of (data.flows || [])) {
        const status = flow.status || (flow.broken ? "error" : flow.enabled ? "active" : "off");
        const card = document.createElement("article");
        card.className = `flow-card ${statusClass(status)}`;
        card.innerHTML = `
          <div class="flow-card-header">
            <div>
              <div class="flow-category">${escapeHtml(flow.category || "Flow")}</div>
              <div class="flow-card-title">${escapeHtml(flow.name)}</div>
            </div>
            <span class="status-pill ${statusClass(status)}">● ${escapeHtml(statusLabels[status] || statusLabels.unknown)}</span>
          </div>
          <div class="flow-detail">${escapeHtml(flow.detail || "")}</div>
          <div class="flow-meta">
            <span>Enabled: <strong>${flow.enabled ? "ja" : "nee"}</strong></span>
            <span>Broken: <strong>${flow.broken ? "ja" : "nee"}</strong></span>
          </div>
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
