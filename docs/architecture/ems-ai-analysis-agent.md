# EMS AI Analysis Agent V0.2

## Scope

The EMS AI Analysis Agent is a **read-only diagnostic and explanation layer**.
It is not part of the realtime control loop and has no device-write path.

V0.2 keeps the proven V0.1 power/performance evidence and adds the evidence
needed to explain *why* EV control did or did not execute, plus a bounded
read-only Pi/EMS health snapshot.

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

V0.2 retains:

1. `EMS_PI_DAY_PERFORMANCE_V0.1`;
2. planner-history coverage exposed through that report;
3. bounded 5-minute P1, aggregate PV and Tesla electrical-power evidence.

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

This event history is **observability only**. It is never consumed by the
planner, Gate or actuator.

### Pi / EMS health evidence

`/usr/local/bin/ems-health` produces `EMS_PI_HEALTH_V0.1` and follows the
operator-health structure:

- **SYSTEM** — uptime, load, memory, disk, Pi temperature and throttling flag;
- **EMS DATA** — freshness/existence of canonical runtime data and history;
- **EMS FUNCTIONS** — expected active services/timers and their last systemd
  result/status;
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

`POST /agent/ask` accepts a question and day. The response contains the
answer plus bounded evidence counts/status. Raw model responses and credentials
are not persisted.
