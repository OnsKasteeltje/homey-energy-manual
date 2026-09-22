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

  // P1 is the independent realtime grid-boundary authority. Positive signed
  // grid power means import; negative means export. PV freshness must never
  // invalidate P1 or realtime control.
  const p1Valid = raw?.balance?.control_gate?.grid_measurement_valid === true;

  const pvSources = [
    {key: "solarEdge", label: "SolarEdge", power: number(raw?.pv?.solaredge_w)},
    {key: "goodWe4200", label: "GoodWe 4200", power: number(raw?.pv?.goodwe_4200_w)},
    {key: "goodWe2000", label: "GoodWe 2000", power: number(raw?.pv?.goodwe_2000_w)}
  ].map((source) => ({
    ...source,
    fresh: raw?.pv?.sources?.[source.key]?.fresh === true,
    ageSec: number(raw?.pv?.sources?.[source.key]?.age_sec),
    maxAgeSec: number(raw?.pv?.sources?.[source.key]?.max_age_sec)
  }));

  const freshPvSources = pvSources.filter((source) => source.fresh && source.power !== null).length;
  const pvQuality = freshPvSources === pvSources.length && pv !== null
    ? "MEASURED"
    : freshPvSources > 0 ? "PARTIAL" : "STALE";

  // Exact realtime household consumption is DERIVED, never synonymous with
  // P1 net power. Publish it only when both P1 and aggregate PV are reliable.
  // signed grid: +import / -export, hence house = PV + signed P1.
  const house = p1Valid && pvQuality === "MEASURED" ? Math.max(0, pv + grid) : null;
  const houseQuality = house === null ? "UNKNOWN" : "DERIVED";

  // "Other" remains a legacy derived reconstruction. It is independent from
  // the exact-house presentation and must not be invented from stale PV.
  const other = number(raw?.energy_budget?.other_house_load_w);
  const deadline = formatLocalTime(raw?.tesla?.deadline_at);

  return {
    generatedAt: raw?.meta?.generated_at ?? null,
    stateAgeSec: number(raw?.meta?.state_age_sec),
    p1Valid,
    grid, pv, pvSources, pvQuality, freshPvSources, house, houseQuality,
    tesla, ww, heat, other,
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
  const response = await fetch(SOURCE, {cache: "no-store"});
  if (!response.ok) throw new Error(`energy-state HTTP ${response.status}`);
  return normalize(await response.json());
}
