import {batteryView, acDirectionText, batteryValue} from "../state/battery-state.mjs";
const SOURCE = "/web/live/battery";
const set = (id, value) => {
  const el = document.getElementById(id);
  if (el) el.textContent = value ?? "—";
};
function render(raw) {
  const s = batteryView(raw);
  const quality = {
    FRESH: "Actueel · Pi-meting",
    STALE: "Vertraagd · geen actuele waarden",
    PARTIAL: "Onvolledige meetset",
    UNAVAILABLE: "Niet beschikbaar"
  };
  set("battery-quality", quality[s.status] || "Niet beschikbaar");
  set("battery-soc", batteryValue(s.socPct, "%"));
  set("battery-ac-power", batteryValue(s.acPowerW, "W", 0));
  set("battery-power-detail", acDirectionText(s.acPowerW));
  set("battery-charged", batteryValue(s.chargeTotalKWh, "kWh"));
  set("battery-discharged", batteryValue(s.dischargeTotalKWh, "kWh"));
  // One independent AlphaESS reading drives both the read-only detail panel
  // and the neutral topology node. No inferred charge/discharge direction.
  set("battery-flow-power", batteryValue(s.acPowerW, "W", 0));
  set("battery-flow-status", s.status === "FRESH"
    ? "Richting onbevestigd" : "Niet actueel");
  const link = document.getElementById("battery-flow-link");
  if (link) link.textContent = "↕";
  const t = Date.parse(s.sampledAtUtc ?? "");
  const label = Number.isFinite(t) ? new Intl.DateTimeFormat("nl-NL", {
    timeZone: "Europe/Amsterdam", day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit"
  }).format(t) : "—";
  set("battery-freshness", s.status === "FRESH"
    ? "Laatste volledige Pi-meting: " + label + " · " + s.ageSec + " s oud"
    : "Geen actuele batterijmeting · laatst geregistreerd: " + label);
}
async function refreshBattery() {
  try {
    const response = await fetch(SOURCE, {cache:"no-store"});
    if (!response.ok) throw new Error("battery endpoint unavailable");
    render(await response.json());
  } catch {
    render({status:"UNAVAILABLE"});
  }
}
refreshBattery();
setInterval(refreshBattery, 30000);
