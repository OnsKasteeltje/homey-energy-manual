# EM v2 | 05 Config | EMS Settings Sync v0.4 TARGETED 15-MIN LOW-LOAD

_Status: GitHub preparation complete through Logic-ID resolution. Homey deployment not performed._

## Objective

Replace v0.3's broad 5-minute `Homey.logic.getVariables()` scan with deterministic targeted Logic reads, keep the existing GitHub `ems_settings` command contract, and reduce steady-state polling cadence from 5 to 15 minutes while retaining manual triggerability.

## Compatibility with live Core v0.11f

Validated 2026-08-30 against live `EM v2 | 00 Core Tick | v0.11f (Planner Tesla Headroom)`.

The Settings Sync interface is unchanged by v0.11f:

- `EMS_ContractType` remains the canonical website/config contract selector consumed by the Contract Price Adapter;
- `EMS_HotWaterSource` remains the canonical BOILER/CV selector;
- `WW_Boilermodus` remains the boolean warm-water mode consumed by Core (`state.hotWater.mode`);
- FIXED/DYNAMIC contract changes must never alter `EMS_HotWaterSource` or `WW_Boilermodus` unless the website command explicitly changes `hotWaterSource`;
- Core v0.11f's Planner Tesla projected-grid headroom change does not alter this contract;
- no Core, Planner, Power Intent, WW Adapter/Gate/Actuator or EV ownership is moved into Settings Sync.

## Low-load requirements

v0.4 must satisfy all of the following:

- no `Homey.logic.getVariables()`;
- no `Homey.devices.getDevices()`;
- no variable creation during normal runtime;
- targeted reads/writes only by stable Logic ID;
- 15-minute scheduled cadence + manual start;
- same `ems_settings` GitHub command schema;
- same canonical outputs: `EMS_ContractType`, `EMS_HotWaterSource`, `WW_Boilermodus`;
- `requestId` idempotency retained;
- status writes only when state meaningfully changes or an error state changes;
- no physical device/actuator writes.

## Stable Logic ID registry

All IDs are now resolved. The final two were resolved with exactly two targeted Homey autocomplete reads; no flow list, Logic enumeration, device discovery or mutation was used.

- `EMS_ContractType`: `8d346495-f183-4072-86d0-c4bc9da94e2e`
- `EMS_HotWaterSource`: `63006c48-7b92-452c-bbf5-6c02893b875c`
- `WW_Boilermodus`: `f9d885a4-fca2-4aea-a5a9-a5c05da90835`
- `EMS_Settings_LastRequestId`: `e5562ce6-8ca9-4fff-af68-43fa183f0d23`
- `EMS_Settings_Sync_Status`: `9f643c3c-0db9-4a8e-8b34-d0d0c49de220`
- `GH_Status_Token`: `235cfe0f-5760-48b9-9349-a33be47d04d1`

There are zero remaining runtime placeholders.

## Runtime source

The exact script is stored separately as:

`src/homey/config/ems-settings-sync-v0.4-targeted-15min.js`

Production properties:

- six targeted Logic reads per scheduled/manual run;
- GitHub command fetch after those targeted reads;
- zero writes on the common already-applied path;
- writes only for changed canonical values/requestId/status;
- zero broad Logic/device enumeration;
- zero physical device writes.

## Flow topology target

- Existing flow ID retained: `9193b3ae-1e3d-4b52-aa95-60aff099e68a`.
- Rename to `EM v2 | 05 Config | EMS Settings Sync v0.4 TARGETED 15-MIN LOW-LOAD`.
- Scheduled trigger: every 15 minutes.
- Manual start retained.
- One HomeyScript action only.
- Keep flow disabled during the in-place code/cadence update; enable only for the controlled acceptance run.

The exact current card UUID/topology must be fetched once immediately before deployment so the in-place update preserves the live Advanced Flow structure rather than inventing card IDs. That single read is the only remaining Homey discovery call required for deployment preparation.

## Acceptance test — DYNAMIC -> FIXED with WW isolation

1. Fetch the current Settings Sync Advanced Flow once and generate the exact in-place update payload outside Homey.
2. Apply one Advanced Flow update with v0.4 runtime + 15-minute cadence, initially disabled.
3. Capture pre-test values for `EMS_HotWaterSource` and `WW_Boilermodus` using targeted validation only.
4. Enable v0.4 and apply one controlled website DYNAMIC -> FIXED command while leaving `hotWaterSource=BOILER` unchanged.
5. Confirm `EMS_ContractType=FIXED` and the new requestId is applied.
6. Confirm `EMS_HotWaterSource` and `WW_Boilermodus` are unchanged from pre-test values: contract switching must cause no WW-mode transition in Core v0.11f.
7. Confirm Contract Price Adapter publishes `EM2_Contract_Type=FIXED`, `source=FIXED_CONFIG_TARGETED`, `horizon=STATIC`, with no PBTH call.
8. No `list_flows`, no broad Logic scan and no improvised probe fan-out during this acceptance run.
9. Leave v0.4 enabled only after the acceptance result is PASS and no unexpected 429/throttling behavior is observed.

## Separate load-map item

Live Core v0.11f still contains one 5-minute `Homey.logic.getVariables()` broad read. That is a separate optimization item and must not be mixed into this Settings Sync change. v0.4 removes the second recurring broad scan that v0.3 would otherwise add.

## Release decision

Prepared outside Homey: **YES**.

Runtime IDs complete: **YES**.

Homey mutation during this preparation: **NO**.

Remaining Homey discovery before deployment: **one `get_advanced_flow` on the Settings Sync flow only**.

Ready to generate exact deployment payload after that single read: **YES**.
