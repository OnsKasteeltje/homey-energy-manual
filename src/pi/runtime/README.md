# HEMS Pi shadow runtime v0.1

Status: **PREPARED / NOT DEPLOYED / SHADOW_READ_ONLY / NO PHYSICAL WRITES**

This is the first executable Raspberry Pi runtime skeleton. It is intentionally narrow: it proves process lifecycle, configuration, structured logging, local health reporting and one live read-only price-source path while reusing the existing source-managed price normalizer and selector under `src/homey/context/`.

## What v0.1 does

- Requires Node.js 20 or newer.
- Reads `config.json`, or falls back to `config.example.json` for preparation/testing.
- Fetches EnergyZero public quarter-hour prices.
- Normalizes them through `price-source-normalizer-v0.1.mjs`.
- Runs `price-source-selector-v0.1.mjs` in shadow mode.
- Emits structured JSON logs to stdout.
- Exposes local-only `GET /health` and `GET /state` on `127.0.0.1:8787` by default.
- Runs every 15 minutes by default, or once with `npm run once`.

## What v0.1 deliberately does not do

- No Homey Logic writes.
- No device writes.
- No EV or WW actuator ownership.
- No Victron control.
- No DESS replacement logic.
- No Planner execution yet.
- No PBTH live read from the Pi yet. PBTH remains disabled until a read-only Pi-side bridge/input contract has been designed and validated.

The runtime contains a hard guard that refuses to run if any write flag in the configuration is enabled.

## First Pi smoke sequence

After the Pi is installed and the repository is checked out:

```bash
cd src/pi/runtime
cp config.example.json config.json
npm run check
npm run once
```

Expected result: JSON log records with `RUNTIME_STARTED` and `PRICE_SHADOW_CYCLE`. The cycle may report `NO_ELIGIBLE_SOURCE` when the EnergyZero response for the requested local date alone does not reach the configured 24-hour forward horizon. That is evidence about source horizon, not permission to relax the safety rules.

For service mode:

```bash
npm start
```

Then from the Pi itself:

```bash
curl http://127.0.0.1:8787/health
```

## Packaging decision remains open

This skeleton does not decide Docker versus native Node/systemd. The runtime is dependency-free and can support either packaging model. A systemd unit should only be added/promoted after the actual Pi filesystem location, runtime user, restart behavior, log retention and deployment procedure are fixed.

## Next implementation gate

The next useful step is not actuator migration. It is:

1. run this skeleton on the actual Pi;
2. record a clean one-shot and restart smoke;
3. add a read-only PBTH bridge/input contract or an equivalent independent source;
4. perform Pi-vs-current-runtime A/B price/context parity;
5. only then wire Planner v0.4.7 semantics into Pi shadow execution.
