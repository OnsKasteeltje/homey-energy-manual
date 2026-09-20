const API_ROOT = "/web/history";

function pad(value) { return String(value).padStart(2, "0"); }
function localParts(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Amsterdam", year: "numeric", month: "2-digit", day: "2-digit"
  }).formatToParts(date);
  return Object.fromEntries(parts.map(p => [p.type, p.value]));
}
export function todayAmsterdam() {
  const p = localParts();
  return `${p.year}-${p.month}-${p.day}`;
}
export function requestValue(kind, anchor) {
  if (kind === "day" || kind === "week") return anchor;
  if (kind === "month") return anchor.slice(0, 7);
  return anchor.slice(0, 4);
}
export function shiftAnchor(kind, anchor, direction) {
  const [y,m,d] = anchor.split("-").map(Number);
  const date = new Date(Date.UTC(y, m - 1, d, 12));
  if (kind === "day") date.setUTCDate(date.getUTCDate() + direction);
  if (kind === "week") date.setUTCDate(date.getUTCDate() + 7 * direction);
  if (kind === "month") date.setUTCMonth(date.getUTCMonth() + direction);
  if (kind === "year") date.setUTCFullYear(date.getUTCFullYear() + direction);
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth()+1)}-${pad(date.getUTCDate())}`;
}
export async function loadHistory(kind, anchor) {
  const value = requestValue(kind, anchor);
  const response = await fetch(`${API_ROOT}/${kind}/${encodeURIComponent(value)}`, {cache:"no-store"});
  if (!response.ok) throw new Error(`History API ${response.status}`);
  const data = await response.json();
  if (data.schema !== "EMS_WEB_HISTORY_V1") throw new Error("Onbekend history-schema");
  return data;
}