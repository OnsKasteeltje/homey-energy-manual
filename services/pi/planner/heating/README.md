# Heating planner

Canonical Pi heating-planner boundary. Current functionality is READ_ONLY / SHADOW only.

`build_heating_preheat_plan.py` preserves Honeywell as comfort authority and exposes only upcoming Honeywell `UP` transitions as preheat candidates. It does not consume a separate PV-opportunity schema and does not select a PV slot itself. Baseline Honeywell heating remains comfort demand; only earlier/additional preheat may later enter the joint Dynamic Pi Planner when forecast PV-export potential exists.

Heating Preheat V0.3 adds a second local-only safety/observability layer in `build_heating_preheat_shadow_v0_3.py`. It combines the room model, V0.2 candidate plan and fresh Quatt observer state to expose baseline-heating/CV guards and the next thermally legal step. It does not grant PV opportunity, choose a physical target or write devices.

`run_heating_preheat_shadow_v0_3.py` composes the local derived artifacts for commissioning. Physical control remains outside this directory's current scope.
