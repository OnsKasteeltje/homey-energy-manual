const SOURCE = "../../data/energy-state-v2.json";

const number = (value) => Number.isFinite(Number(value)) ? Number(value) : null;

export function formatPower(value) {
  const w = number(value);
  if (w === null) return "—";
  if (Math.abs(w) >= 1000) return `${(w / 1000).toFixed(1).replace(".", ",")} kW`;
  return `${Math.round(w)} W`;
}

export function formatLocalTime(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("nl-NL", {
    timeZone: "Europe/Amsterdam", hour: "2-digit", minute: "2-digit"
  }).format(date);
}

export function normalize(raw) {
  const grid = number(raw?.grid?.power_w);
  const pv = number(raw?.pv?.total_w);
  const tesla = number(raw?.tesla?.power_w);
  const ww = number(raw?.hot_water?.boiler_power_w);
  const heat = number(raw?.quatt?.power_w);
  const house = number(raw?.energy_budget?.house_load_w);
  const known = [tesla, ww, heat].filter((v) => v !== null).reduce((a,b) => a+b, 0);
  const other = house === null ? null : Math.max(0, house - known);
  const deadline = formatLocalTime(raw?.tesla?.deadline_at);

  return {
    generatedAt: raw?.meta?.generated_at ?? null,
    stateAgeSec: number(raw?.meta?.state_age_sec),
    balanceValid: raw?.balance?.valid === true,
    grid, pv, house, tesla, ww, heat, other,
    gridDirection: grid === null ? "onbekend" : grid > 0 ? "import" : grid < 0 ? "export" : "in balans",
    teslaConnected: raw?.tesla?.connected === true,
    teslaCharging: raw?.tesla?.charging === true,
    teslaRequestedA: number(raw?.tesla?.requested_a),
    teslaDeadline: deadline,
    teslaDeadlineActive: raw?.tesla?.deadline_active === true,
    teslaNeed: raw?.tesla?.need ?? null,
    wwOn: raw?.hot_water?.boiler_on === true,
    wwAction: raw?.hot_water?.control?.action ?? null,
    heatOn: raw?.quatt?.thermostat_heating_on === true,
    managerDecision: raw?.manager?.decision ?? null,
    managerReason: raw?.manager?.reason ?? null,
    managerPriority: raw?.manager?.priority ?? null
  };
}

export async function loadState() {
  const response = await fetch(`${SOURCE}?t=${Date.now()}`, {cache: "no-store"});
  if (!response.ok) throw new Error(`energy-state HTTP ${response.status}`);
  return normalize(await response.json());
}
