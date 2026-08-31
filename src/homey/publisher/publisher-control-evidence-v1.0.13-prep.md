# Publisher v1.0.13 CONTROL EVIDENCE — PREPARED OUTSIDE HOMEY

Status: **PREPARED / NOT DEPLOYED / HOMEY ID BINDING PENDING**

Goal: extend the existing scheduled low-load public-state publisher with a read-only `control_evidence` section so the Planner page can compare the current Planner slot against actual Power Intent and adapter output without introducing any physical write path.

## Runtime contracts to publish

The publication layer must copy the existing runtime objects as-is:

- `EM2_Power_Intent` (`EM2_POWER_INTENT_V0.2`)
- `EM2_EV_Power_Adapter` (`EM2_EV_POWER_ADAPTER_V0.1`)
- `EM2_WW_Power_Adapter` (`EM2_WW_POWER_ADAPTER_V0.1`)

No EV current, executable power, WW state or revision may be reconstructed by the publisher. The publisher is observability-only.

## Canonical web shape

```json
{
  "control_evidence": {
    "schema": "EM2_CONTROL_EVIDENCE_V0.1",
    "generatedAt": "...",
    "readOnly": true,
    "observabilityOnly": true,
    "controlImpact": "NONE",
    "power_intent": { "...raw EM2_Power_Intent...": "..." },
    "adapter": {
      "ev": { "...raw EM2_EV_Power_Adapter...": "..." },
      "warm_water": { "...raw EM2_WW_Power_Adapter...": "..." }
    },
    "revisions": {
      "powerIntent": 0,
      "evAdapter": 0,
      "wwAdapter": 0,
      "aligned": false
    },
    "complete": false,
    "safety": {
      "deviceWritesIntroduced": false,
      "derivedValues": false,
      "rawRuntimeContracts": true
    }
  }
}
```

Reference implementation: `src/homey/publisher/control-evidence-contract-v0.1.mjs` with unit tests in `tests/control-evidence-contract.test.mjs`.

## Low-load integration rule

Do **not** add a broad `Homey.logic.getVariables()` scan. After the existing 15-minute publisher gate has passed, add exactly three targeted Logic reads for the three runtime contracts above. Reads must happen only when a GitHub publication is already due; they must not create an additional trigger or publication cadence.

Known stable ID:

- `EM2_Power_Intent`: `04b57041-dd7f-41f7-a00a-f023afb1ccee`

Still requires one-time Homey binding before deployment:

- `EM2_EV_Power_Adapter`: ID pending
- `EM2_WW_Power_Adapter`: ID pending

These IDs must be read once and then hard-bound. Do not discover them by a collection scan on every publisher run.

## Publisher merge fragment

The exact current Homey v1.0.12 source is not yet captured in GitHub, so this is deliberately a merge fragment rather than a guessed full replacement.

```js
// only after existing <=1/15min publish gate says a publication is due
const [intentV,evAdapterV,wwAdapterV]=await Promise.all([
  Homey.logic.getVariable({id:ID.powerIntent}),
  Homey.logic.getVariable({id:ID.evPowerAdapter}),
  Homey.logic.getVariable({id:ID.wwPowerAdapter})
]);
const powerIntent=parse(intentV?.value);
const evAdapter=parse(evAdapterV?.value);
const wwAdapter=parse(wwAdapterV?.value);
const nr=v=>Number.isFinite(Number(v))?Number(v):null;
const ir=nr(powerIntent?.sourceRevision),er=nr(evAdapter?.sourceRevision),wr=nr(wwAdapter?.sourceRevision);
payload.control_evidence={
  schema:'EM2_CONTROL_EVIDENCE_V0.1',
  generatedAt:now,
  readOnly:true,
  observabilityOnly:true,
  controlImpact:'NONE',
  power_intent:powerIntent||null,
  adapter:{ev:evAdapter||null,warm_water:wwAdapter||null},
  revisions:{powerIntent:ir,evAdapter:er,wwAdapter:wr,aligned:ir!==null&&er===ir&&wr===ir},
  complete:!!powerIntent&&!!evAdapter&&!!wwAdapter,
  safety:{deviceWritesIntroduced:false,derivedValues:false,rawRuntimeContracts:true}
};
```

## Acceptance gates before deployment

1. Capture/read back exact current Publisher v1.0.12 HomeyScript and reconcile it into GitHub first.
2. Bind both adapter variable IDs with targeted one-time reads.
3. Confirm the three additional reads occur only after the existing 15-minute hard gate has passed.
4. Confirm no trigger changes and no additional GitHub PUT cadence.
5. Confirm `control_evidence.power_intent` preserves `EM2_POWER_INTENT_V0.2` unchanged.
6. Confirm EV `command.requested_A` and `electrical.executable_W` are copied, not recomputed.
7. Confirm WW `command.value` is copied, not inferred from boiler state.
8. Confirm any missing/invalid input is published as null/incomplete rather than synthesized.
9. Confirm no physical device write and no actuator ownership change.
10. One SHADOW publication smoke followed by website revision/alignment check.

## Expected Homey load delta

Current publisher remains one scheduled publication opportunity per 15 minutes. New work is **+3 targeted Logic reads only on an already-due publication**. No new poller, trigger, device read, collection scan or external publication is introduced.
