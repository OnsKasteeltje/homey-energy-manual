# Homey bulk capture resume marker — 2026-08-28

Status: paused due to Homey `Too many requests` during read-only detail capture.

## Successfully captured before pause
- EM v2 | 70 Planner | WW Scheduling SHADOW v0.2
- EM v2 | 50 Decision | WW Seasonal Source Advisor v0.3 SHADOW idempotent
- EM v2 | 50 Decision | WW Post-Goal Opportunity v0.4 SHADOW

## Resume from
1. EM v2 | 70 History | Day Series v0.5.4 — flow id `14027232-905e-4b8b-828d-5b44b8f6692e`
2. EM v2 | 70 History | Control Audit v0.4 low-load — flow id `df295b26-9a47-497a-87c7-ccfd32323db1`
3. EM v2 | 72 History | Immutable Day Archive v0.1 — flow id `322bcfe6-1ec4-46d4-a840-d13009d9c9c9`
4. EM v2 | 76 Evidence | BC Planner Intent Recorder v0.4 local-first — flow id `9aba3344-b8b4-423f-9132-b606990b9ffe`
5. Remaining 80/81/90 Validation and Observability flows.

Do not rerun `list_flows` before resuming unless the Homey inventory is known to have changed.

Capture is read-only. No smoke test is required until a captured flow is actually refactored/deployed/promoted on Homey.
