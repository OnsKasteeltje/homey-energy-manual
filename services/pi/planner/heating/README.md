# Heating planner

Canonical Pi heating-planner boundary. Current functionality is READ_ONLY / SHADOW only.

`build_heating_preheat_plan.py` preserves Honeywell as comfort authority and exposes only upcoming Honeywell `UP` transitions as preheat candidates. It does not consume a separate PV-opportunity schema and does not select a PV slot itself. Baseline Honeywell heating remains comfort demand; only earlier/additional preheat may later enter the joint Dynamic Pi Planner when forecast PV-export potential exists.

Physical control is outside this directory's current scope.
