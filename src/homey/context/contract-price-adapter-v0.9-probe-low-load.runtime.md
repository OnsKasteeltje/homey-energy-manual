# EM v2 | 30 Context | Contract Price Adapter v0.9 PROBE LOW-LOAD

- Homey flow ID: `69648157-892b-49d2-bc4d-e61a1a4d78ab`
- Type: Advanced Flow
- Runtime state at creation: `enabled=true`, `broken=false`, `triggerable=true`
- Trigger: manual start only
- Purpose: validate a low-load dynamic-price context path before adding any recurring schedule.

## Low-load design

The probe intentionally removes the two broad runtime enumerations used by v0.8:

- no `Homey.logic.getVariables()`
- no `Homey.devices.getDevices()`

Instead it uses:

1. PBTH `prices_json(next_hours)` Flow card as the only PBTH read.
2. `TEMP_PBTH_JSON_BUFFER` as the price-buffer handoff.
3. Targeted `Homey.logic.getVariable({id})` reads for only the canonical contract selector and price buffer.
4. Targeted `Homey.logic.updateVariable({id,...})` writes for the mirror and compact price-context diagnostics.
5. No actuator/device writes.

## Targeted variable IDs

- `EMS_ContractType`: `8d346495-f183-4072-86d0-c4bc9da94e2e`
- `EM2_Contract_Type`: `211e5846-aada-4607-8d52-01b2ef578866`
- `TEMP_PBTH_JSON_BUFFER`: `29ffd8d7-b0ae-4c02-ab5a-c62452a7b70b`
- `EM2_ContractPrice_Context`: `93e41221-6b4d-4f5f-83dc-997c9620f758`
- `EM2_ContractPrice_Source`: `3e5a182d-2479-479a-bb58-42a27f4a4e23`
- `EM2_ContractPrice_Quality`: `abedc6f4-cfee-4496-9b3c-418f1f3ad2bc`
- `EM2_ContractPrice_Horizon`: `587ea957-f9e9-44c7-b975-3bed53bd9ab8`
- `EM2_ContractPrice_UpdatedAt`: `77e16ec7-9ebb-4488-9caf-47c1ab3d4ddb`

## Probe output contract

For `DYNAMIC`, v0.9 publishes `EM2_UNIFORM_PRICE_CONTEXT_V0.4` with `quality`, `updatedAt`, first-slot import price, horizon, slot count and explicit guards stating that no broad enumerations or actuator writes occurred.

For non-dynamic mode the probe does not build a dynamic price context; fixed-contract handling remains with the existing architecture until the probe is promoted.

## Promotion gate

Do not add a 15-minute trigger until a single controlled probe proves that Planner v0.4.8 reports:

- `inputs.price.quality = GOOD`
- `inputs.price.fresh = true`
- `inputs.price.usable = true`
- WW remainder moves to `GRID_CHEAPEST_USABLE` where applicable.

The v0.8 adapter remains disabled during this validation.
