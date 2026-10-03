# EMS AI Analysis Agent V0.3

## Scope

The EMS AI Analysis Agent is a **read-only diagnostic and explanation layer**.
It is not part of the realtime control loop and has no device-write path.

V0.3 keeps the proven V0.2 EV/control and health evidence and broadens the
read-only context needed to explain whole-EMS decisions: tracked flexible loads,
frozen planner decisions around the question timestamp, and a no-hindsight
PV forecast-versus-actual comparison.

Runtime chain:

```text
Homey canonical state
      |
      +--> POST /state/energy
      |       +--> energy-state-v2.json
      |       +--> ems-history.sqlite
      |             +--> P1 / PV / Tesla power
      |             +--> EV connected / charging / requested+offered A
      |             +--> phase currents / deadline context
      |             +--> EMS manager decision / reason
      |
Homey EV observability
      |
      +--> targeted Logic reads only
      +--> POST /state/ev-control
              +--> ems-history.sqlite / ev_control_events
                    +--> Gate result/errors
                    +--> actuator status/reason
                    +--> requested/confirmed phase and current
                    +--> transition stage/failure
                    +--> device-health reason

Pi runtime
      |
      +--> /usr/local/bin/ems-performance
      +--> /usr/local/bin/ems-health
      +--> planner-history.sqlite (frozen decision snapshots)
      +--> ems-history.sqlite measurements_15m + pv_forecast_v2_archive
      |
      v
ems-ai-analysis.service (127.0.0.1:3210)
      |
      v
configured language model
```

Frontend V2 uses the same private LAN/Tailscale ingress as V0.1. GitHub is not
a runtime evidence transport for the AI agent.

## Safety boundary

- `readOnly=true`
- `controlWrites=false`
- no Homey, Easee, Tesla, boiler, Honeywell or other physical-write client exists
  in the AI service;
- the AI service does not call the Pi control endpoint;
- the dedicated Homey EV evidence push performs targeted Logic reads only and
  has no device reads, Logic writes, device writes or planning decisions;
- `/state/ev-control` only validates and archives observability evidence;
- model output is explanatory text and is never converted into an EMS command.

The model must distinguish **Feit**, **Afleiding** and **Advies** and must state
when evidence is insufficient. An observed export window is not by itself proof
of an EMS fault.

## Evidence model

### Performance and electrical timeline

V0.3 retains `EMS_PI_DAY_PERFORMANCE_V0.1` and expands the bounded 5-minute
electrical timeline to P1, aggregate PV, Tesla, boiler and Quatt power plus
washer/dryer active state when available. A derived residual household value is
included only as a labelled derivation from measured house power minus the
tracked large loads; it is not a new measurement authority.

### Planner decision window

For question-specific timestamps the agent extracts a bounded historical
`plannerDecisionWindow` from `planner-history.sqlite`. The question may provide
an explicit local clock time (for example `14:00`); otherwise the analysis uses
important export windows and recent control events as anchors.

For each anchor V0.3 selects the latest frozen planner snapshot generated at or
before that timestamp. It never reads the current planner output and pretends it
was historical state. Only a compact projection is sent to the model: relevant
realtime correction context, deadline/guardrail context and the 15-minute action
covering the anchor, including EV/WW/battery targets and recorded planner
reasons. Snapshots older than the bounded historical tolerance remain missing
rather than being fabricated.

### PV forecast versus actual

V0.3 adds `forecastVsActual15m` from canonical local history. Forecast values
come from `pv_forecast_v2_archive` using the same fixed 12-hour no-hindsight
selection rule as PV & Flex: for each target slot use the newest forecast that
already existed no later than slot start minus 12 hours. Actual PV/export and
EV/boiler context come from canonical `measurements_15m`.

The evidence contains a daily comparable-slot summary (forecast energy, actual
energy, bias and mean absolute error) plus a bounded detail set around analysis
anchors and the largest forecast-error/export slots. A later forecast must
never be used to judge an earlier planner decision.

### Canonical EV telemetry history

The existing Homey -> Pi state push already contains EV telemetry. V0.2 archives
the following fields into canonical `ems-history.sqlite`:

- connected / charging;
- requested and offered current;
- L1/L2/L3 measured current;
- charge state;
- deadline active, deadline maximum current and remaining kWh;
- EV need;
- EMS manager decision, reason and priority.

Observed phase mode may be derived from measured phase currents for correlation.
When an explicit actuator/control event exists, its commanded and confirmed
phase fields are the stronger explanation evidence.

### EV control event history

Homey's existing runtime contracts already expose the important reason chain:
Power Intent -> Adapter -> Gate -> Actuator -> Device Health. V0.2 transports
those snapshots over the trusted LAN to `POST /state/ev-control` and stores
them in `ev_control_events`.

The event archive includes Gate PASS/FAIL and errors, actuator status/reason,
requested current and phase, confirmed phase, transition stage/failure,
charge-state/device-health context and whether the actuator reports a physical
write.

Identical runtime evidence triggered repeatedly is deduplicated semantically.
The event hash is derived from the normalized persisted evidence fields rather
than the raw transport payload, so top-level and nested volatile timestamps do
not create history noise. A real Gate, actuator, transition, charge-state or
health change still produces a distinct event.
The ingest additionally compares incoming normalized evidence with the latest
persisted normalized event before hash-based insertion. This preserves semantic
dedupe across hash-algorithm upgrades without rewriting existing history.

This event history is **observability only**. It is never consumed by the
planner, Gate or actuator.

### Pi / EMS health evidence

`/usr/local/bin/ems-health` produces `EMS_PI_HEALTH_V0.1` and follows the
operator-health structure:

- **SYSTEM** — uptime, load, memory, disk, Pi temperature and throttling flag;
- **EMS DATA** — freshness/existence of canonical runtime data and history;
- **EMS FUNCTIONS** — expected active long-running services, plus for timer-driven
  functions both the active timer schedule and the last triggered `.service`
  execution/result; an active timer alone is not proof that the function works;
- **RECENT INCIDENT SIGNALS** — best-effort warning/error journal evidence for
  EMS systemd units over the previous 24 hours.

The overall health state is `HEALTHY`, `HEALTHY_WITH_RECENT_INCIDENTS` or
`DEGRADED`.

Current health is context, not historical proof. A healthy Pi now does not prove
that every component was healthy at an earlier EV decision timestamp.

## Historical boundary

The richer EV telemetry and EV control-event history starts when V0.2 is
commissioned. Earlier days must not be backfilled by inference.

Recent incident signals are a bounded best-effort journal view, not yet a
durable incident ledger. A later version may persist incident transitions if
that proves useful.

## SQLite read boundary

AI/performance readers open live history with SQLite `mode=ro` and
`PRAGMA query_only=ON`. The AI systemd sandbox grants the bounded
`ReadWritePaths=/home/jeroen/ems/data` filesystem carve-out required for live
WAL/SHM coordination. The SQL connections remain read-only.

`immutable=1` must not be used by AI readers against the live operational
history.

## Model configuration

Host-local credentials remain in:

`/etc/ems/ai-agent.env`

Expected secret:

```text
OPENAI_API_KEY=...
```

Optional model override:

```text
EMS_AI_MODEL=gpt-6-luna
```

Secrets must never be committed.

## API

`GET /agent/health` reports readiness and the configured model without
exposing credentials.

`POST /agent/ask` accepts a question and day. The question is also used only to
select bounded historical analysis anchors; it never changes EMS state. The
response contains the answer plus bounded evidence counts/status. Raw model
responses and credentials are not persisted.

## Runtime model tuning

The analysis model is configured through the systemd service environment.

- `EMS_AI_MODEL` selects the OpenAI model.
- `EMS_AI_REASONING_EFFORT` selects reasoning effort; the application default is `medium`.
- `EMS_AI_MAX_OUTPUT_TOKENS` limits the combined reasoning and answer output budget; the application default is `1200`.

The deployed analysis service may deliberately use a higher reasoning effort and output-token ceiling than the application defaults. These settings affect analysis only and do not grant control-write authority.
