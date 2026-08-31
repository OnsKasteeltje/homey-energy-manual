# Publisher v1.0.13 CONTROL EVIDENCE

Status: **DEPLOYED / NATURAL PUBLICATION SMOKE PENDING**

Goal: extend the scheduled low-load public-state publisher with a read-only `control_evidence` section so the Planner page can compare the current Planner slot against actual Power Intent and adapter output without introducing any physical write path.

## Deployed runtime contracts

The publication layer copies these existing runtime objects as-is:

- `EM2_Power_Intent` (`EM2_POWER_INTENT_V0.2`) — ID `04b57041-dd7f-41f7-a00a-f023afb1ccee`
- `EM2_EV_Power_Adapter` (`EM2_EV_POWER_ADAPTER_V0.1`) — ID `f2118322-d59d-4aa8-b478-234effc3983c`
- `EM2_WW_Power_Adapter` (`EM2_WW_POWER_ADAPTER_V0.2`) — ID `686181b9-e135-40fe-b09d-df5928269466`

Exact deployed source is captured in `src/homey/publisher/publisher-v1.0.13-control-evidence.js`.

No EV current, executable power, WW state or revision is reconstructed by the publisher. The publisher is observability-only.

## Canonical web shape

```json
{
  "control_evidence": {
    "schema": "EM2_CONTROL_EVIDENCE_V0.1",
    "generatedAt": "...",
    "readOnly": true,
    "observabilityOnly": true,
    "controlImpact": "NONE",
    "power_intent": {},
    "adapter": {"ev": {}, "warm_water": {}},
    "revisions": {"powerIntent": 0, "evAdapter": 0, "wwAdapter": 0, "aligned": false},
    "complete": false,
    "safety": {"deviceWritesIntroduced": false, "derivedValues": false, "rawRuntimeContracts": true}
  }
}
```

Reference implementation: `src/homey/publisher/control-evidence-contract-v0.1.mjs`; unit tests: `tests/control-evidence-contract.test.mjs`.

## Low-load implementation

The existing v1.0.12 structure is preserved:

- same 15-minute cron;
- same +8 s phase offset;
- same six targeted Logic reads before the publication gate;
- no `Homey.logic.getVariables()` collection scan.

Only after the existing publication gate has passed, v1.0.13 performs exactly three additional targeted Logic reads for Power Intent, EV Adapter and WW Adapter. No extra trigger, poller or GitHub publication cadence is introduced.

## Runtime deployment result

Homey flow `fe84bc17-72d4-4fbb-9a69-b3d751b0ffcd` is now named `EM v2 | 40 Data | Publisher v1.0.13 CONTROL EVIDENCE LOW-LOAD` and readback after update reported:

- `enabled=true`
- `broken=false`
- triggerable=true
- schedule unchanged: every 15 minutes
- delay unchanged: 8 seconds
- no device-read or actuator-write code added

The deployment was performed after capturing the exact v1.0.12 HomeyScript and binding the adapter output IDs from the exact enabled adapter flows.

## Remaining acceptance gate

Do not force a publication inside the 15-minute gate. Let the next natural scheduled publication run. PASS requires:

1. `meta.publisher_version = EM2_PUBLISHER_V1.0.13`;
2. `control_evidence.schema = EM2_CONTROL_EVIDENCE_V0.1`;
3. raw Power Intent schema remains `EM2_POWER_INTENT_V0.2`;
4. EV adapter publishes raw `command.requested_A` and `electrical.executable_W`;
5. WW adapter publishes raw `command.value` and schema `EM2_WW_POWER_ADAPTER_V0.2`;
6. `control_evidence.complete=true` when all three objects are present;
7. revision alignment is reported truthfully, never synthesized;
8. no physical write or actuator ownership change occurs.

## Expected Homey load delta

Current publisher remains one scheduled publication opportunity per 15 minutes. New work is **+3 targeted Logic reads only on an already-due publication**. No new poller, trigger, device read, collection scan or external publication is introduced.
