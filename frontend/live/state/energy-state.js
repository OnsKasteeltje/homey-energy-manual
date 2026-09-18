const SOURCE = "../../data/energy-state-v2.json";

const number = (value) => {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

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
  // House load is a derived value and is only shown when the canonical
  // Homey Core balance is valid. Fresh P1 remains authoritative for grid
  // import/export even when stale PV telemetry makes house load unknown.
  const canonicalHouse = number(raw?.energy_budget?.house_load_w);
  const balanceValid = raw?.balance?.valid === true;
  const house = balanceValid ? canonicalHouse : null;
  const known = [tesla, ww, heat].filter((v) => v !== null).reduce((a,b) => a+b, 0);
  const other = house === null ? null : Math.max(0, house - known);
  const deadline = formatLocalTime(raw?.tesla?.deadline_at);

  return {
    generatedAt: raw?.meta?.generated_at ?? null,
    stateAgeSec: number(raw?.meta?.state_age_sec),
    balanceValid,
    grid, pv, house, tesla, ww, heat, other,
    gridDirection: grid === null ? "onbekend" : grid > 0 ? "import" : grid < 0 ? "export" : "in balans",
    teslaConnected: raw?.tesla?.connected === true,
    teslaCharging: raw?.tesla?.charging === true,
    teslaRequestedA: number(raw?.tesla?.requested_a),
    teslaDeadline: deadline,
    teslaDeadlineActive: raw?.tesla?.deadline_active === true,
    teslaNeed: raw?.tesla?.need ?? null,
    teslaRemainingKWh: number(raw?.tesla?.remaining_kwh),
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
