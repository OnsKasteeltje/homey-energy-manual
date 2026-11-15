/**
 * EMS Live V0.4: presentation-only power evidence.
 * The energy hub is a topology illustration, never a power-balance proof.
 * P1 signed power (+ import / - export) is independent of battery telemetry.
 * Existing pv+grid excludes independent AC battery accounting, so do not
 * display it as household load or invent an "Other" residual.
 */
export function flowView(state) {
  const p1 = state?.p1Valid === true && Number.isFinite(state?.grid)
    ? state.grid : null;
  const gridDirection = p1 === null ? "onbekend"
    : p1 > 0 ? "import" : p1 < 0 ? "export" : "in balans";
  const pv = state?.pvQuality === "MEASURED" &&
    Number.isFinite(state?.pv) && state.pv >= 0 ? state.pv : null;
  return {
    gridPowerW: p1 === null ? null : Math.abs(p1),
    gridDirection,
    gridArrow: p1 === null || p1 === 0 ? "↔" : p1 > 0 ? "→" : "←",
    pvPowerW: pv,
    pvArrow: pv !== null && pv > 0 ? "→" : "—",
    housePowerW: null,
    otherPowerW: null,
    houseExplanation: pv === null ? "PV-data onvoldoende · accubijdrage onbekend"
      : "Accubijdrage niet gevalideerd",
    qualityText: "Huisverbruik en residu niet vastgesteld met actieve thuisaccu",
    gridSummary: p1 === null ? "Net · P1 niet actueel"
      : "Net · " + (p1 === 0 ? "in balans" : gridDirection),
  };
}
