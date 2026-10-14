import {loadState, formatPower, formatLocalTime} from "../state/energy-state.js";
import {diagnoseDishwasher} from "../diagnostics/dishwasher-fingerprint.mjs";

const DISHWASHER_HISTORY_KEY = "ems-live-dishwasher-l1-diagnostics-v1";
function readDishwasherHistory() {
  try {
    const rows = JSON.parse(localStorage.getItem(DISHWASHER_HISTORY_KEY) || "[]");
    return Array.isArray(rows) ? rows : [];
  } catch { return []; }
}
let dishwasherHistory = readDishwasherHistory();
function dishwasherDiagnosis(state) {
  const result = diagnoseDishwasher(state, dishwasherHistory);
  const changed = result.history.length !== dishwasherHistory.length ||
    result.history.at(-1)?.ts !== dishwasherHistory.at(-1)?.ts;
  dishwasherHistory = result.history;
  if (changed) {
    try { localStorage.setItem(DISHWASHER_HISTORY_KEY, JSON.stringify(dishwasherHistory)); }
    catch { /* storage is optional; live read-only display still works */ }
  }
  return result;
}


const $ = (id) => document.getElementById(id);
const set = (id, value) => { const el=$(id); if (el) el.textContent=value ?? "—"; };

function pvAge(source) {
  if (source.ageSec === null) return "geen tijdstempel";
  const age = source.ageSec < 60 ? `${Math.round(source.ageSec)} s geleden` : `${Math.round(source.ageSec / 60)} min geleden`;
  return source.fresh ? age : `${age} · vertraagd`;
}

function pvQualityText(s) {
  if (s.pvQuality === "MEASURED") return `${s.freshPvSources}/${s.pvSources.length} bronnen actueel · gemeten`;
  if (s.pvQuality === "PARTIAL") return `${s.freshPvSources}/${s.pvSources.length} bronnen actueel · gedeeltelijk`;
  if (s.pvQuality === "NIGHT") return "nacht · 0 W verwacht";
  return "PV-data vertraagd";
}

function pvSourceSummary(s) {
  const total = s.pvSources.length;
  const warning = s.freshPvSources < total ? " ⚠" : " ✓";
  return `${s.freshPvSources}/${total} actueel${warning}`;
}

function currentPvPower(s) {
  return s.pvQuality === "MEASURED" || s.pvQuality === "NIGHT" ? s.pv : null;
}

function sourcePowerText(source) {
  if (!source) return "—";
  return source.fresh ? formatPower(source.power) : `laatste ${formatPower(source.power)}`;
}

function applianceStatus(value) {
  return value === true ? "Actief" : value === false ? "Niet actief" : "Onbekend";
}

function applianceDetail(item) {
  if (item.active === null) return "Homey-status ontbreekt";
  if (!item.active) return "Geen programma actief";
  return [item.cyclePhase, item.applianceState]
    .filter(Boolean).join(" · ") || "Programma actief";
}

function dishwasherStatus(d) {
  switch (d.status) {
    case "LIKELY": return "Waarschijnlijk";
    case "CANDIDATE": return "Kandidaat";
    case "UNCONFIRMED": return "Niet bevestigd";
    case "NO_MATCH": return "Niet herkend";
    case "SUSPENDED": return "Niet beoordeelbaar";
    default: return "Onbekend";
  }
}

function dishwasherDetail(d) {
  switch (d.reason) {
    case "HEAT_AND_PUMP_SEQUENCE": return "L1 · verwarmings- en pomppatroon";
    case "REPEATED_L1_HEATING_NO_PUMP_YET": return "L1 · meerdere verwarmingssamples";
    case "DRYER_PHASE_UNVERIFIED": return "L1 · mogelijke overlap met droger";
    case "ISOLATED_L1_HIGH_LOAD": return "L1 · losse piek, onvoldoende bewijs";
    case "TAIL_AFTER_SEQUENCE": return "L1 · korte rustfase na verwarmingscyclus";
    case "CYCLE_END_CONFIRMED": return "L1 · cyclus beëindigd";
    case "TESLA_MULTIPHASE_INTERFERENCE": return "L1 · Tesla veroorzaakt overlap";
    case "SOLAREDGE_STALE": return "L1 · SolarEdge-data onvoldoende";
    case "P1_STALE": return "L1 · P1-data onvoldoende";
    case "SOURCE_TIMESTAMP_INVALID": return "L1 · geen actuele tijdstempel";
    default: return "L1 · geen onderscheidend patroon";
  }
}

function consumerExplanation(s, dishwasher) {
  if (!s.p1Valid || s.grid === null) return "P1 niet actueel; verbruiksdiagnose tijdelijk niet beschikbaar.";
  const notes = [];
  if (s.loads.washer.active === true)
    notes.push("Wasmachine actief volgens AEG (fase L2 als historische referentie).");
  if (s.loads.dryer.active === true)
    notes.push("Droger actief volgens AEG (fase nog niet gevalideerd).");
  if (dishwasher.status === "LIKELY")
    notes.push("Vaatwasser waarschijnlijk actief volgens L1-sequentie; geen directe vermogensmeting.");
  else if (dishwasher.status === "CANDIDATE")
    notes.push("Vaatwasser kandidaat op L1; nog niet voldoende bewijs om het apparaat te bevestigen.");
  else if (dishwasher.status === "UNCONFIRMED")
    notes.push("Extra L1-belasting gezien, maar één piek bewijst geen vaatwasser.");
  const heavy = s.gridPhases
    .filter((p) => p.power !== null && p.power >= 1500)
    .sort((a, b) => b.power - a.power);
  if (heavy.length > 0 && dishwasher.status !== "LIKELY")
    notes.push("Hoge netto belasting op " + heavy.map((p) => p.name).join(" en ") + ".");
  return notes.length ? notes.join(" ") : "Geen betrouwbaar te onderscheiden grote apparaatbelasting.";
}

function render(s) {
  const dishwasher = dishwasherDiagnosis(s);
  set("pv-power", formatPower(currentPvPower(s)));
  const pvByKey = Object.fromEntries(s.pvSources.map((source) => [source.key, source]));
  set("pv-source-summary", pvSourceSummary(s));
  set("pv-se", sourcePowerText(pvByKey.solarEdge));
  set("pv-se-age", pvByKey.solarEdge ? pvAge(pvByKey.solarEdge) : "—");
  set("pv-gw42", sourcePowerText(pvByKey.goodWe4200));
  set("pv-gw42-age", pvByKey.goodWe4200 ? pvAge(pvByKey.goodWe4200) : "—");
  set("pv-gw20", sourcePowerText(pvByKey.goodWe2000));
  set("pv-gw20-age", pvByKey.goodWe2000 ? pvAge(pvByKey.goodWe2000) : "—");
  set("pv-summary", pvQualityText(s));

  set("grid-power", formatPower(s.grid === null ? null : Math.abs(s.grid)));
  set("grid-direction", s.p1Valid ? s.gridDirection : "P1 niet actueel");
  const gridFlow = $("grid-flow");
  if (gridFlow) {
    gridFlow.classList.toggle("export", s.grid !== null && s.grid < 0);
    gridFlow.classList.toggle("balanced", s.grid === null || s.grid === 0);
  }

  set("house-power", formatPower(s.house));
  set("house-state", s.houseQuality === "DERIVED"
    ? "berekend uit PV + P1"
    : !s.p1Valid ? "P1 niet actueel" : "PV-data onvoldoende");

  set("tesla-power", formatPower(s.tesla));
  set("tesla-state", s.teslaCharging ? `laden${s.teslaRequestedA ? ` · ${s.teslaRequestedA} A` : ""}` : s.teslaConnected ? "aangesloten" : "niet aangesloten");
  const wwFlowNode = $("ww-flow-node");
  if (wwFlowNode) wwFlowNode.hidden = !s.wwBoilerMode;
  set("ww-power", formatPower(s.ww));
  set("ww-state", s.wwOn ? "Boiler · verwarmen" : "Boiler");
  set("heat-power", formatPower(s.heat));
  set("heat-state", s.heatOn ? "warmtevraag" : "stand-by");
  set("other-power", formatPower(s.other));

  set("loads-washer-status", applianceStatus(s.loads.washer.active));
  set("loads-washer-detail", applianceDetail(s.loads.washer));
  set("loads-dryer-status", applianceStatus(s.loads.dryer.active));
  set("loads-dryer-detail", applianceDetail(s.loads.dryer));
  set("loads-dishwasher-status", dishwasherStatus(dishwasher));
  set("loads-dishwasher-detail", dishwasherDetail(dishwasher));
  set("loads-quooker-status", applianceStatus(s.loads.quooker.active));
  set("loads-quooker-detail", !s.loads.quooker.fresh
    ? "Geen actuele Quooker-detectie"
    : s.loads.quooker.active && s.loads.quooker.estimatedPowerW !== null
      ? `${formatPower(s.loads.quooker.estimatedPowerW)} · geschat`
      : "P1-gebaseerde detectie");
  for (const phase of s.gridPhases) {
    set(`loads-phase-${phase.name.toLowerCase()}`,
      s.p1Valid ? formatPower(phase.power) : "—");
  }
  set("loads-explanation", consumerExplanation(s, dishwasher));

  set("kpi-grid", formatPower(s.grid === null ? null : Math.abs(s.grid)));
  set("kpi-grid-sub", s.p1Valid ? `${s.gridDirection} · P1 actueel` : "P1 niet actueel");
  set("kpi-pv", formatPower(currentPvPower(s)));
  set("kpi-pv-sub", pvQualityText(s));
  set("kpi-tesla", s.teslaCharging ? "Laden" : s.teslaConnected ? "Aangesloten" : "Niet aangesloten");
  set("kpi-tesla-sub", s.teslaDeadlineActive
    ? [s.teslaDeadline ? `deadline ${s.teslaDeadline}` : null, s.teslaRemainingKWh !== null ? `${s.teslaRemainingKWh.toFixed(2).replace(".", ",")} kWh resterend` : null].filter(Boolean).join(" · ")
    : (s.teslaNeed || "geen deadline actief"));
  set("kpi-ww", s.wwBoilerMode ? "Boiler" : "CV");
  set("kpi-ww-sub", "actieve warmtebron");

  set("manager-priority", s.managerPriority || "EMS");
  set("manager-title", s.managerDecision ? s.managerDecision.replaceAll("_", " ") : "Geen expliciete EMS-beslissing");
  set("manager-reason", s.managerReason || "Actuele toestand; geen beslisreden gepubliceerd.");

  const generated = formatLocalTime(s.generatedAt);
  set("freshness", generated ? `Bijgewerkt ${generated}` : "Live");
}

function renderError(error) {
  set("loads-dishwasher-status", "Onbekend");
  set("loads-dishwasher-detail", "Geen actuele gegevens");
  set("loads-washer-status", "Onbekend");
  set("loads-dryer-status", "Onbekend");
  set("loads-quooker-status", "Onbekend");
  for (const phase of ["l1", "l2", "l3"]) set("loads-phase-" + phase, "—");
  set("loads-explanation", "Live-verbruiksdiagnose niet beschikbaar.");
  set("freshness", "Data niet beschikbaar");
  set("manager-title", "Live data tijdelijk niet beschikbaar");
  set("manager-reason", error.message);
}

async function refresh() {
  try { render(await loadState()); } catch (error) { renderError(error); }
}
refresh();
setInterval(refresh, 15000);
