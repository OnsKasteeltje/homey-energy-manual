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
  if (watts < -100) return "Negatief vermogen · laadrichting onbevestigd";
  return "Rust / laag vermogen";
}
export function batteryValue(value, unit, digits = 1) {
  if (value === null) return "—";
  return value.toLocaleString("nl-NL", {minimumFractionDigits: digits, maximumFractionDigits: digits}) + " " + unit;
}
