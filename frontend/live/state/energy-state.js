const SOURCE = "/web/state/current";

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
  // Canonical House semantics: P1/net power is the source of truth.
  // Positive = net import, negative = net export. PV is a separate flow and
  // must never gate or alter the House KPI.
  const p1Valid = raw?.balance?.control_gate?.grid_measurement_valid === true;
  const house = p1Valid ? grid : null;
  const balanceValid = p1Valid;
  // "Other" remains a legacy derived reconstruction and must not be derived
  // from the P1-net House KPI.
  const other = number(raw?.energy_budget?.other_house_load_w);
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
    wwBoilerMode: raw?.hot_water?.mode === true,
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
