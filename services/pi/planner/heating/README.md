# Heating planner

Canonical Pi heating-planner boundary. Current physical functionality remains READ_ONLY / SHADOW only.

`build_heating_preheat_plan.py` preserves Honeywell as comfort authority and exposes only upcoming Honeywell `UP` transitions as preheat candidates. It does not consume a separate PV-opportunity schema and does not select a PV slot itself. Baseline Honeywell heating remains comfort demand; only earlier/additional preheat may later enter the joint Dynamic Pi Planner when forecast PV-export potential exists.

Heating Preheat V0.3 adds a second local-only safety/observability layer in `build_heating_preheat_shadow_v0_3.py`. It combines the room model, V0.2 candidate plan and fresh Quatt observer state to expose baseline-heating/CV guards and the next thermally legal step. It does not grant PV opportunity, choose a physical target or write devices.

`run_heating_preheat_shadow_v0_3.py` composes the local derived artifacts for commissioning. Physical control remains outside this directory's current scope.

Heating Preheat V0.4 adds a downstream **stateful progression SHADOW** in `build_heating_preheat_progression_shadow_v0_4.py`. It consumes only the already-derived V0.3 Heating shadow, Flex Priority Shadow V0.1 and its own previous local shadow artifact. V0.4 may persist a hypothetical active `+0.5 C` step and advance it only after measured room-temperature proof, while preserving the V0.3 CV/baseline guards and the central planner grant requirement.

For grouped opportunities such as `living_area`, a subsequent step waits until all selected rooms have reached their currently active shadow target. Loss of planner grant holds progression; it does not invent rollback behavior. `rollbackBehavior = NOT_DEFINED_SHADOW_ONLY` is explicit until a future LIVE actuator contract is designed.

`run_heating_preheat_progression_shadow_v0_4.py` publishes `/home/jeroen/ems/data/heating-preheat-progression-shadow-v0.4.json`. The entire V0.4 layer remains READ_ONLY / SHADOW, performs no network call and has no physical write path.

## Production Dynamic Pi Planner Heating grant V0.1

`build_heating_production_grant_v0_1.py` defines the next planner boundary without creating a separate Heating planner or a separate PV budget. It combines:

- the current authoritative Dynamic Pi Planner slot;
- V0.3 Heating eligibility/safety;
- Flex Priority V0.1 central Heating↔EV arbitration;
- fresh canonical P1 import/export state.

The output schema is `EMS_PI_DYNAMIC_HEATING_GRANT_V0.1`. Forecast opportunity and realtime permission are deliberately separate. The shared planner opportunity is read from the existing slot's `evResidualExportW`, i.e. the common residual after non-EV planned flex and before EV acts as residual consumer when Heating owns first claim. No Heating watt reservation is invented: `powerReservationW=0`.

Fresh P1 is the realtime authority. Forecast alone can never produce `PRODUCTION_GRANT`; conversely, fresh measured export may authorize an otherwise valid Heating grant even when the current forecast slot did not predict export. Any P1 import, stale/ambiguous P1, stale planner state, stale/misordered Heating/Flex state or loss of Heating priority fails closed to `HOLD`.

V0.1 is a **planner grant only**. `controlWrites=false` and `physicalWriteAllowed=false` remain hard invariants. The parked Pi→Homey Heating SHADOW publisher is not resumed by this increment. V0.4 is not switched to this contract until the grant builder, replay/contract tests and architecture gate have passed.
