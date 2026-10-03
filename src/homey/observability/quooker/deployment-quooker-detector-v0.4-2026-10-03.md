# Quooker detector v0.4 deployment

Date: 2026-10-03

Status: **DEPLOYED / LIVE — observe-only**

## Runtime

Homey Advanced Flow:

`EM v2 | 01 Quooker Detector | v0.4 LIVE OBSERVE-ONLY`

Flow ID:

`e291cf14-0b92-4cef-ae8b-a699692b6c9a`

Canonical HomeyScript source:

`src/homey/observability/quooker/quooker-detector-v0.4.live-homey.js`

Pure classifier:

`src/homey/observability/quooker/quooker-detector-v0.4.mjs`

## Incident

On 2026-10-03 the documented v0.3 Quooker detector and its separate P1 heartbeat flow were no longer present in the live Homey flow inventory.

The Quooker control path itself remained healthy:

```text
Pi / Power Intent
  -> Quooker Adapter
  -> EM2_Control_Quooker
  -> Quooker v0.2 LIVE Actuator
  -> Cooker onoff
```

At 10:11 local time the control path switched the Cooker ON. P1 L3 then moved from approximately `-1290 W` to `+346 W` within five seconds, a `+1636 W` step that matches the expected Quooker heating element. Because no detector flow was running, `EM_Quooker_Power_W` remained 0.

## v0.4 correction

v0.4 restores only observation. It does not write the Cooker.

- every 15 seconds while the flow is enabled;
- immediate run on Cooker ON/OFF;
- targeted Cooker read every run;
- targeted P1 L3 read every run while Cooker ON;
- OFF P1 baseline refresh at approximately 55 seconds;
- no `Homey.devices.getDevices()`;
- no physical device writes.

Heating starts on a 1300..1900 W L3 delta and is held on 1100..2050 W. The non-heating baseline follows current L3 background and is frozen during HEATING.

## Pre-deploy validation

PR #135 passed:

- Quooker detector replay tests: PASS;
- measured `-1290 -> +346 W` trace classified as `HEATING / 1636 W`;
- thermostat top-up replay: PASS;
- switch-OFF authority regression: PASS;
- runtime JavaScript parse: PASS;
- no physical writer regression: PASS;
- EMS Architecture Gate: PASS;
- EMS Security Scan: PASS;
- Software Architecture Build: PASS.

## Initial live verification

The newly created Advanced Flow is:

```text
enabled = true
broken  = false
```

A manual trigger completed without error.

Before recovery the stale detector baseline was approximately `0.1 W`. Immediately after v0.4 started, `EM_Quooker_Baseline_L3_W` moved to the real current L3 background around `-2383 W` and continued following it.

At that verification moment the Cooker was ON but the heating element was not active, so:

```text
EM_Quooker_Power_W = 0 W
```

was the expected result.

## Remaining runtime acceptance

The next natural thermostat heating pulse should produce:

```text
EM_Quooker_Active  = true
EM_Quooker_Status  = HEATING
EM_Quooker_Power_W ≈ 1.3..1.9 kW
```

and Core v0.11p should then include that detected power in `knownMeasuredLoadW`.

No artificial Cooker switching is required solely for validation.
