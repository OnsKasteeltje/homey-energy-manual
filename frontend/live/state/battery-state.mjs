// Independent view model: battery values are never P1, PV or control inputs.
const numeric = v => typeof v === "number" && Number.isFinite(v) ? v : null;
export function batteryView(raw) {
  const trusted = raw?.schema === "EMS_WEB_LIVE_BATTERY_V1" &&
    raw?.status === "FRESH" && raw?.readOnly === true &&
    raw?.eligibleForControl === false && raw?.eligibleForHouseBalance === false;
  const m = trusted ? raw.measurements : null;
  return {
    status: trusted ? "FRESH" : (raw?.status === "FRESH" ? "UNAVAILABLE" : raw?.status ?? "UNAVAILABLE"),
    sampledAtUtc: raw?.sampledAtUtc ?? null,
    ageSec: numeric(raw?.ageSec),
    socPct: numeric(m?.socPct),
    acPowerW: numeric(m?.acPowerW),
    chargeTotalKWh: numeric(m?.chargeTotalKWh),
    dischargeTotalKWh: numeric(m?.dischargeTotalKWh)
  };
}
export function acDirectionText(watts) {
  if (watts === null) return "Geen actuele meting";
  if (watts > 100) return "Ontladen · indicatie";
  if (watts < -100) return "Laden · indicatie (laadteken nog niet gevalideerd)";
  return "Rust / laag vermogen";
}
// Presentation-only AC direction. Positive discharge is independently corroborated
// against Energy Life; negative AC charging is an inference pending direct validation.
// No battery value is fed into P1, PV, household accounting or EMS control.
export function batteryFlowView(state) {
  const watts = state?.status === "FRESH" ? numeric(state?.acPowerW) : null;
  if (watts === null) return {
    direction: "unknown", arrow: "—", status: "Richting onbekend",
    ariaLabel: "Geen actuele, betrouwbare accuvermogensmeting"
  };
  if (watts > 100) return {
    direction: "discharging", arrow: "↑", status: "Naar huis",
    ariaLabel: "Thuisaccu levert " + Math.round(watts) + " watt aan huis"
  };
  if (watts < -100) return {
    direction: "charging", arrow: "↓", status: "Naar accu · indicatie",
    ariaLabel: "Vermoedelijke laadrichting: " + Math.round(-watts) +
      " watt naar accu; negatief AC-laadteken nog niet onafhankelijk gevalideerd"
  };
  return {
    direction: "idle", arrow: "—", status: "Rust / laag vermogen",
    ariaLabel: "Geen duidelijke actieve accustroom bij laag AC-vermogen"
  };
}
export function batteryValue(value, unit, digits = 1) {
  if (value === null) return "—";
  return value.toLocaleString("nl-NL", {minimumFractionDigits: digits, maximumFractionDigits: digits}) + " " + unit;
}
