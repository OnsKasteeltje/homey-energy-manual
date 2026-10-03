# EMS AI Analysis Agent V0.1

## Scope

The EMS AI Analysis Agent is a **read-only diagnostic and explanation layer**.
It is not part of the realtime control loop and has no device-write path.

Runtime chain:

```text
Frontend V2 /ai/
      |
      v
POST /agent/ask
      |
      v
ems-ai-analysis.service (127.0.0.1:3210)
      |
      +--> /usr/local/bin/ems-performance
      |       +--> ems-history.sqlite
      |       +--> planner-history.sqlite
      |
      +--> bounded 5-minute grid/PV/Tesla evidence
      |
      v
configured language model
```

Caddy exposes only the private LAN/Tailscale route already used by Frontend V2.

## Safety boundary

- `readOnly=true`
- `controlWrites=false`
- no Homey, Easee, Tesla, boiler, Honeywell or other physical-write client exists in this service;
- the service does not call the Pi control endpoint;
- it reads canonical history and the standardized `ems-performance` report only;
- absence of a model credential fails explicitly with `MODEL_NOT_CONFIGURED`;
- model output is explanatory text and is never converted into a control command.

The model is instructed to separate **Feit**, **Afleiding** and **Advies** and to
say when evidence is insufficient.

## V0.1 evidence

V0.1 combines:

1. `EMS_PI_DAY_PERFORMANCE_V0.1`;
2. planner-history coverage as already projected by that report;
3. bounded 5-minute averages for P1 grid power, aggregate PV power and Tesla
   electrical power.

This is sufficient for the first question family around PV export versus EV
charging, but it does not yet contain historical EV requested current, phase
mode or actuator reason codes. Those remain explicit limitations rather than
being inferred.

## Model configuration

The service reads an optional root-owned environment file:

`/etc/ems/ai-agent.env`

Expected secret:

```text
OPENAI_API_KEY=...
```

Optional model override:

```text
EMS_AI_MODEL=gpt-6-luna
```

Secrets must never be committed to GitHub.

## API

`GET /agent/health`

Reports readiness and the configured model without exposing credentials.

`POST /agent/ask`

Example request:

```json
{"question":"Waarom exporteerden we vandaag terwijl de Tesla aangesloten was?","day":"today"}
```

The response contains the answer plus a small evidence summary. Raw model
responses and API keys are not persisted.
