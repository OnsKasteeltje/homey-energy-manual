# Pi WW replay v0.1

Status: OFFLINE / SHADOW PREPARATION

## Scope

This replay slice implements the exact source-managed translation semantics currently available in GitHub for:

- `EM v2 | 60 Adapter | WW Power v0.1 SHADOW`

The captured Homey contract accepts `EM2_POWER_INTENT_V0.2`, requires `valid=true`, `deviceWrites=false`, a numeric source revision, and a present `targets.ww.target_on` whose value is boolean or null. It translates only to the boiler `onoff` command semantics:

- `true` -> `OK_ON` / command `true`
- `false` -> `OK_OFF` / command `false`
- `null` -> `OK_HOLD` / command `null`
- invalid input -> `INVALID_POWER_INTENT` / command `null`

The adapter performs no policy decision, device reads, device writes, Insights, polling, or network calls.

## Pi implementation

`src/pi/ems/ww_semantics.py` reproduces this contract as a pure deterministic function. The implementation is always read-only and emits `physicalWrite=false`.

`src/pi/replay_runner.py` now includes WW adapter output in `PI_EMS_REPLAY_REPORT_V0.2` when a fixture contains a `ww_adapter` section.

The integrated fixture `replay_ev_ww_publish.json` verifies one combined chain:

```text
Core projection
  -> EV semantic HOLD
  -> WW Power Intent translation = ON
  -> Publisher revision event
```

No external I/O occurs during replay.

## Safety cases covered

- valid WW ON;
- valid WW HOLD;
- rejection when `deviceWrites=true` reaches this SHADOW contract;
- rejection when WW target is missing;
- physical writes remain impossible in the replay implementation.

## Important source gap

The currently active Homey architecture uses newer WW components (`WW Power v0.2 TARGETED-READ SHADOW`, `WW Power Adapter Gate v0.2 TARGETED-READ`, and Warm Water Actuator v0.9 TARGETED-READ LIVE). Their exact current runtime source is not yet captured in GitHub.

Therefore this replay is a **contract seed**, not a claim of full parity with the active WW chain.

Do not promote Pi WW ownership on the basis of this v0.1 replay.

## Next required captures

Before full Homey <-> Pi WW parity testing:

1. capture exact active `WW Power v0.2 TARGETED-READ SHADOW` source;
2. capture exact active `WW Power Adapter Gate v0.2 TARGETED-READ` source;
3. capture exact active `Warm Water Actuator v0.9 TARGETED-READ LIVE` source;
4. capture WW Scheduling/Decision inputs and outputs;
5. add gate rejection cases and actuator-command envelope to replay;
6. compare identical Homey and Pi inputs in SHADOW before any ownership transfer.
