/**
 * EV Power Adapter v0.1 — SHADOW
 *
 * Deterministic translation from device-independent EV power intent [W]
 * to a theoretically executable Easee current setpoint [A].
 *
 * No device writes are performed by this module.
 */

export const EV_POWER_ADAPTER_REVISION = "EV_POWER_ADAPTER_V0.1";

const DEFAULTS = Object.freeze({
  phaseCount: 3,
  voltageV: 230,
  minCurrentA: 6,
  maxIntentAgeMs: 120_000,
  maxChargerStateAgeMs: 120_000,
});

function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function failClosed({
  targetW,
  theoreticalA = null,
  reason,
  inputFresh = false,
  chargerState = null,
  confirmedA = null,
  sourceRevision = null,
  timestamp,
}) {
  const normalizedTargetW = isFiniteNumber(targetW) ? targetW : null;
  return {
    schema: EV_POWER_ADAPTER_REVISION,
    mode: "SHADOW",
    deviceWrites: false,
    targetW: normalizedTargetW,
    theoreticalA,
    requestedA: 0,
    executableW: 0,
    deltaW: normalizedTargetW != null ? -Math.max(normalizedTargetW, 0) : null,
    reason,
    inputFresh,
    chargerState,
    commandedA: null,
    confirmedA: isFiniteNumber(confirmedA) ? confirmedA : null,
    sourceRevision,
    timestamp,
  };
}

/**
 * Map one EV power intent into a SHADOW actuator request.
 *
 * Policy decisions such as PV smoothing, hysteresis, MUST/deadline priority
 * and opportunity charging remain upstream in Energy Core.
 */
export function mapEvPowerIntent(input) {
  const nowMs = input?.nowMs ?? Date.now();
  const timestamp = new Date(nowMs).toISOString();

  const phaseCount = input?.phaseCount ?? DEFAULTS.phaseCount;
  const voltageV = input?.voltageV ?? DEFAULTS.voltageV;
  const minCurrentA = input?.minCurrentA ?? DEFAULTS.minCurrentA;
  const maxCurrentA = input?.maxCurrentA;
  const maxIntentAgeMs = input?.maxIntentAgeMs ?? DEFAULTS.maxIntentAgeMs;
  const maxChargerStateAgeMs =
    input?.maxChargerStateAgeMs ?? DEFAULTS.maxChargerStateAgeMs;

  const targetW = input?.targetW;
  const sourceRevision = input?.sourceRevision ?? null;
  const chargerState = input?.chargerState ?? null;
  const confirmedA = input?.confirmedA ?? null;

  if (!isFiniteNumber(targetW) || targetW < 0) {
    return failClosed({
      targetW,
      reason: "INVALID_INTENT",
      chargerState,
      confirmedA,
      sourceRevision,
      timestamp,
    });
  }

  if (
    !Number.isInteger(phaseCount) ||
    phaseCount <= 0 ||
    !isFiniteNumber(voltageV) ||
    voltageV <= 0 ||
    !isFiniteNumber(minCurrentA) ||
    minCurrentA <= 0 ||
    !isFiniteNumber(maxCurrentA) ||
    maxCurrentA <= 0 ||
    !isFiniteNumber(maxIntentAgeMs) ||
    maxIntentAgeMs < 0 ||
    !isFiniteNumber(maxChargerStateAgeMs) ||
    maxChargerStateAgeMs < 0
  ) {
    return failClosed({
      targetW,
      reason: "INVALID_CONSTRAINTS",
      chargerState,
      confirmedA,
      sourceRevision,
      timestamp,
    });
  }

  const maxExecutableCurrentA = Math.floor(maxCurrentA);
  if (maxExecutableCurrentA < minCurrentA) {
    return failClosed({
      targetW,
      reason: "MAX_CURRENT_BELOW_MINIMUM",
      chargerState,
      confirmedA,
      sourceRevision,
      timestamp,
    });
  }

  const intentTimestampMs = input?.intentTimestampMs;
  if (
    !isFiniteNumber(intentTimestampMs) ||
    intentTimestampMs > nowMs ||
    nowMs - intentTimestampMs > maxIntentAgeMs
  ) {
    return failClosed({
      targetW,
      reason: "STALE_INTENT",
      chargerState,
      confirmedA,
      sourceRevision,
      timestamp,
    });
  }

  if (input?.chargerAvailable !== true) {
    return failClosed({
      targetW,
      reason: "CHARGER_UNAVAILABLE",
      chargerState,
      confirmedA,
      sourceRevision,
      timestamp,
    });
  }

  const chargerStateTimestampMs = input?.chargerStateTimestampMs;
  if (
    !isFiniteNumber(chargerStateTimestampMs) ||
    chargerStateTimestampMs > nowMs ||
    nowMs - chargerStateTimestampMs > maxChargerStateAgeMs
  ) {
    return failClosed({
      targetW,
      reason: "STALE_CHARGER_STATE",
      chargerState,
      confirmedA,
      sourceRevision,
      timestamp,
    });
  }

  if (targetW === 0) {
    return {
      schema: EV_POWER_ADAPTER_REVISION,
      mode: "SHADOW",
      deviceWrites: false,
      targetW,
      theoreticalA: 0,
      requestedA: 0,
      executableW: 0,
      deltaW: 0,
      reason: "ZERO_INTENT",
      inputFresh: true,
      chargerState,
      commandedA: null,
      confirmedA: isFiniteNumber(confirmedA) ? confirmedA : null,
      sourceRevision,
      timestamp,
    };
  }

  const wattsPerAmp = phaseCount * voltageV;
  const theoreticalA = targetW / wattsPerAmp;
  let requestedA = Math.floor(theoreticalA + Number.EPSILON);

  if (requestedA < minCurrentA) {
    return failClosed({
      targetW,
      theoreticalA,
      reason: "BELOW_MINIMUM_EXECUTABLE_POWER",
      inputFresh: true,
      chargerState,
      confirmedA,
      sourceRevision,
      timestamp,
    });
  }

  requestedA = Math.min(requestedA, maxExecutableCurrentA);
  const executableW = requestedA * wattsPerAmp;
  const deltaW = executableW - targetW;

  return {
    schema: EV_POWER_ADAPTER_REVISION,
    mode: "SHADOW",
    deviceWrites: false,
    targetW,
    theoreticalA,
    requestedA,
    executableW,
    deltaW,
    reason:
      requestedA === maxExecutableCurrentA && theoreticalA > maxExecutableCurrentA
        ? "CLAMPED_TO_MAX_CURRENT"
        : deltaW < 0
          ? "QUANTIZED_DOWN"
          : "EXECUTABLE",
    inputFresh: true,
    chargerState,
    commandedA: null,
    confirmedA: isFiniteNumber(confirmedA) ? confirmedA : null,
    sourceRevision,
    timestamp,
  };
}
