import {loadState, formatPower, formatLocalTime} from "../state/energy-state.js";

const $ = (id) => document.getElementById(id);
const set = (id, value) => { const el=$(id); if (el) el.textContent=value ?? "—"; };

function render(s) {
  set("pv-power", formatPower(s.pv));
  set("grid-power", formatPower(s.grid === null ? null : Math.abs(s.grid)));
  set("grid-direction", s.gridDirection);
  set("house-power", formatPower(s.house));
  set("balance-state", s.balanceValid ? "balans geldig" : "balans beperkt");
  set("tesla-power", formatPower(s.tesla));
  set("tesla-state", s.teslaCharging ? `laden${s.teslaRequestedA ? ` · ${s.teslaRequestedA} A` : ""}` : s.teslaConnected ? "aangesloten" : "niet aangesloten");
  set("ww-power", formatPower(s.ww));
  set("ww-state", s.wwOn ? "verwarmen" : (s.wwAction || "uit"));
  set("heat-power", formatPower(s.heat));
  set("heat-state", s.heatOn ? "warmtevraag" : "stand-by");
  set("other-power", formatPower(s.other));

  set("kpi-grid", formatPower(s.grid === null ? null : Math.abs(s.grid)));
  set("kpi-grid-sub", s.gridDirection);
  set("kpi-pv", formatPower(s.pv));
  set("kpi-tesla", s.teslaCharging ? "Laden" : s.teslaConnected ? "Aangesloten" : "Niet aangesloten");
  set("kpi-tesla-sub", s.teslaDeadlineActive && s.teslaDeadline ? `deadline ${s.teslaDeadline}` : (s.teslaNeed || "geen deadline actief"));
  set("kpi-ww", s.wwOn ? "Aan" : "Uit");
  set("kpi-ww-sub", s.wwAction || "—");

  set("decision", s.managerDecision || "Geen actieve beslissing");
  set("decision-reason", s.managerReason || "—");
  set("decision-priority", s.managerPriority || "—");
  set("manager-priority", s.managerPriority || "—");
  set("manager-title", s.managerDecision ? s.managerDecision.replaceAll("_", " ") : "Live energiestroom");
  set("manager-reason", s.managerReason || "Actuele EMS-toestand");

  const generated = formatLocalTime(s.generatedAt);
  set("freshness", generated ? `Bijgewerkt ${generated}` : "Live");
}

function renderError(error) {
  set("freshness", "Data niet beschikbaar");
  set("manager-title", "Live data tijdelijk niet beschikbaar");
  set("manager-reason", error.message);
}

async function refresh() {
  try { render(await loadState()); } catch (error) { renderError(error); }
}
refresh();
setInterval(refresh, 15000);
