# AlphaESS VitaPower 3600 AC — future Pi integration

**Status: PREPARATION ONLY (23 October 2026).** This directory currently contains documentation only: no runtime integration, networking code, service, device command, register map, test runner, or deployment hook. Do not interpret this README as evidence that the Pi can read or control the battery.

## Selected hardware and ownership

- Ordered: **1 x AlphaESS VitaPower 3600 AC — 8 kWh** and **1 x AlphaESS P1 Meter**; not yet commissioned.
- The battery/BMS retains autonomous, safe realtime charge/discharge operation.
- The Pi owns EMS planning and may *later* provide bounded strategic constraints. Homey must not become another competing battery controller.
- If Modbus is supported for this exact firmware/device, its connection has a **single Pi owner**. Confirm supported register semantics, access control and the maximum number of clients before enabling any Modbus read/write path.
- Credentials, local addresses, register overrides, and any access secrets belong only in private Pi configuration, not GitHub.

## Proposed observation contract (not yet published)

Candidate schema identifier: `EMS_ALPHAESS_BATTERY_STATE_V0.1` (no producer or consumer currently implemented).

| Field | Meaning |
| --- | --- |
| `schema`, `source` | Explicit schema and `ALPHAESS_MODBUS_TCP` provenance |
| `generatedAt`, `observedAt` | UTC generation time and actual device sample timestamp, never invented |
| `available`, `readOnly` | Explicit read availability; `readOnly=true` until a separate approved cutover |
| `battery.socPct` | SoC percentage, or `null` when unverified |
| `battery.powerW` | Signed measured battery power: **positive discharge to AC, negative charge from AC**; or `null` |
| `battery.chargedKWh`, `battery.dischargedKWh` | Device counters *only when available and correctly defined*; otherwise `null` |
| `battery.fault` | Observed fault/health diagnostic, or `null` if not established |

These names are a **proposed Pi-normalized interface**, not AlphaESS Modbus register names. Do not publish an invented SoC, power value, counter or register; do not convert missing/stale battery readings to 0. Consumers must check source, freshness and availability. A nominal 8 kWh unit is not proof of 8 kWh usable capacity.

## Future integration sequence (all separately gated)

1. Obtain the VitaPower-specific Modbus register list, firmware compatibility and commissioning evidence; establish the local connection and verify identity **read-only**.
2. Confirm sign convention, SoC and power quality, timestamps, counter behavior, outages/reconnect and (if provided) phase allocation against observed P1 measurements. Continue shadow-only evaluation.
3. Model grid and house power without counting battery charging as house demand or battery discharge as PV production. P1 import/export remains the grid authority; battery energy must be accounted for separately in savings evaluations.
4. Only after documented safety controls and explicit approval consider a bounded, single-owner physical-write path with SoC reserve, Tesla deadline/WW priorities, 3x25 A per-phase limits, write timeouts, stale-data rejection and a safe autonomous fallback.

No existing EMS planner, Homey flow, EV/WW/Quooker actuator, status API or SQLite schema is changed by this preparation. No additional polling timer or GitHub Actions workflow is introduced.

## Related architecture

- `docs/architecture/CURRENT-EMS-STATE.md` — canonical battery boundary and commissioning state.
- `docs/architecture/ems-software-architecture-live.md` — existing reserved `targets.battery.target_W`; **not an active battery writer**.
- `docs/architecture/ems-process-ww-tesla-planner.md` — existing priority order and safety policy.
