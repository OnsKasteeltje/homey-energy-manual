# EMS AI Analysis Agent V0.4

## Scope

The EMS AI Analysis Agent is a **read-only diagnostic and explanation layer**.
It is not part of the realtime control loop and has no device-write path.

V0.4 keeps the proven V0.3 performance, planner, forecast and EV evidence and
adds the historical context needed to explain flexible-load opportunities
across Quooker, warm water and Heating. It remains a read-only diagnostic layer;
no new planner or physical-write authority is introduced.

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
      |       +--> ems-history.sqlite / ev_control_events
      |
Homey Quooker observability
      |
      +--> targeted Logic reads only
      +--> POST /state/quooker
              +--> ems-history.sqlite / quooker_control_events
                    +--> adapter/control target + reason
                    +--> versioned actuator mode + desired/actual state
                    +--> LIVE write proof when physicalWritePerformed=true
                    +--> detector status / measured pulse power

Pi local flex state
      |
      +--> Heating V0.3 eligibility
      +--> Flex Priority V0.1
      +--> Heating V0.4 progression SHADOW
      +--> WW input / seasonal advice / current source
              +--> planner-history.sqlite / flex_context_snapshots

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

### V2 conversation continuity

Frontend V2 keeps the visible AI conversation in browser `sessionStorage`, so
switching to another V2 page and returning in the same tab does not erase the
question/answer history.

Long-running model requests use a browser-generated `requestId`. When present,
the analysis service records only the UI job lifecycle/result in the local
`/home/jeroen/ems/data/ai-analysis-jobs.sqlite` cache. This cache is not EMS
measurement, planner or control state and is never consumed by realtime EMS
logic. Completed entries are retained for at most 24 hours.

`POST /agent/ask` remains compatible with requests that omit `requestId`.
With a request ID it becomes idempotent: a duplicate request cannot start a
second model call while the first is pending, and a completed response is
returned from the local job cache. `GET /agent/result?requestId=...` lets the
browser recover a pending/completed result after page navigation. A pending job
older than the bounded stale interval may be reclaimed with the same ID, which
covers an AI-service/Pi restart without creating an unbounded duplicate path.

The result is persisted before the HTTP response is written. Therefore a
browser disconnect during navigation may discard its socket without discarding
the completed analysis. The AI service remains read-only with respect to EMS
state and physical control; this bounded UI result cache is the only write added
for navigation continuity.

## Safety boundary

- `readOnly=true`
- `controlWrites=false`
- no Homey, Easee, Tesla, boiler, Honeywell or other physical-write client exists
  in the AI service;
- the AI service does not call the Pi control endpoint;
- the dedicated Homey EV and Quooker evidence pushes perform targeted Logic
  reads only and have no device reads, Logic writes, device writes or planning
  decisions;
- `/state/ev-control` and `/state/quooker` only validate and archive
  observability evidence;
- the local flex-context archive reads already-derived Pi artifacts only and
  performs no network/Homey/device call;
- Heating progression remains SHADOW;
- Quooker actuator evidence is versioned. Historical v0.1 evidence may be
  `SHADOW`; v0.2 is `LIVE`. Only explicit LIVE actuator evidence with
  `physicalWritePerformed=true` proves a Homey physical device write;
- `physicalWritePerformed=false` on the LIVE actuator may be an idempotent
  no-op when desired and actual state already matched;
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

Directly observed appliance state in `timeline5m` is first-class diagnostic
evidence. When a power event is analysed and a relevant state such as
`washerActive=true` or `dryerActive=true` is present in the corresponding
interval, the model must mention that state as a **Feit**. Relevance is
question-specific: an observed device state must not be surfaced merely because
it exists in the evidence. For a subsystem-specific question such as whether
the Tesla charged, unrelated washer/dryer state is omitted unless it materially
explains or constrains the Tesla event being analysed. Device-active state does
not by itself prove power attribution: without separate measured device-power
evidence the model may describe the active device as a supported possible
explanation, but must not claim that it caused the measured P1 change.

When the user's question contains one or more explicit local clock times, the
large day-wide historical arrays `timeline5m`, `evTelemetry5m`,
`evControlEvents` and `quookerEvents` are scoped to ±30 minutes around
those user-provided times. Multiple explicit times use the union of their local
windows. The evidence includes `evidenceSelection.mode=EXPLICIT_TIME_WINDOW`,
the explicit anchors and the configured window size, so the model can
distinguish deliberate selection from missing history. Absence outside such a
window must never be interpreted as evidence that no activity occurred there.
When the question contains no explicit clock time, these four arrays retain the
existing bounded day-scope behavior; fallback planner/export anchors must not
silently trigger evidence trimming.

For an in-progress local day, performance quality separates three different
concepts: `dayProgressPct` (how much of the calendar day has elapsed),
`coveragePctFullDay` (integrated evidence as a fraction of the complete day)
and `coveragePctElapsed` / `elapsedCoverageStatus` (how complete the
measurements are for the time that has actually elapsed). `PARTIAL_TODAY`
therefore means the day is still in progress, not that the elapsed evidence is
necessarily incomplete. The legacy `coveragePct` field remains as the
full-calendar-day percentage for compatibility.


### Planner decision window

For question-specific timestamps the agent extracts a bounded historical
`plannerDecisionWindow` from `planner-history.sqlite`. The question may provide
an explicit local clock time (for example `14:00`); otherwise the analysis uses
important export windows and recent control events as anchors.

For each anchor V0.3 selects the latest frozen planner snapshot generated at or
before that timestamp. It never reads the current planner output and pretends it
was historical state. Only a compact projection is sent to the model: relevant
realtime correction context, deadline/guardrail context and the canonical
15-minute planner slot covering the anchor, including EV/WW/Quooker allocation,
phase/current targets and recorded planner reasons. Snapshots older than the bounded historical tolerance remain missing
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

### Historical Heating and warm-water flex context

V0.4 archives a compact semantic snapshot of the already-derived local flex
state in `planner-history.sqlite/flex_context_snapshots`. The source is
`services/pi/history/archive_flex_context_snapshot.py`, run once per minute
after Heating progression.

The snapshot contains bounded projections of:

- Heating Preheat V0.3 eligibility, baseline-demand and CV guards;
- Flex Priority V0.1 owner/grant/reason;
- Heating Preheat V0.4 progression state, measured room temperature,
  hypothetical active step and completion state;
- current WW planner input, current hot-water source and boiler observation;
- WW seasonal-source advice/economic context when available.

Unchanged semantic state is deduplicated, with a bounded heartbeat so the
archive still proves continuing coverage. The archive never reconstructs
earlier state from the current JSON files. Historical coverage therefore starts
only when the V0.4 archive is commissioned.

### Quooker observability history

V0.4 keeps Quooker out of the canonical Core snapshot and adds a separate,
authenticated, control-neutral evidence path. Homey source
`apps/homey/observability/quooker/quooker-pi-push-v0.1.homeyscript.js` reads
only existing Logic contracts for Quooker Control, versioned Actuator Status
and the Quooker detector diagnostic. It posts to `POST /state/quooker`; Pi-side
validation and persistence live in
`services/pi/integrations/homey/ingress/quooker_evidence_ingest.py`.

Accepted snapshots are semantically deduplicated in
`ems-history.sqlite/quooker_control_events`. The archive distinguishes the
planner/adapter mode and target, actuator schema/mode, desired state,
v0.1 SHADOW actual/would-write state, v0.2 LIVE actual-before/actual-after state,
write error and detector-observed switch/heating state. For v0.2 LIVE,
top-level actuator `physicalWritePerformed=true` is preserved as direct
evidence that Homey executed a physical Cooker write. Historical rows retain
their raw JSON, allowing the analysis reader to recover v0.2 LIVE fields from
events captured before the normalized schema was extended. Missing/UNKNOWN
mode remains missing evidence and is never inferred from detector HEATING.

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

### EV deadline relevance semantics

Deadline evidence can legitimately retain fields such as `deadlineAt` and
`remainingKWh` after a command becomes inactive or after its historical
deadline has passed. V0.4.1 therefore annotates EV deadline evidence with
`deadlineSemantics` relative to the timestamp being analysed.

Only `deadlineSemantics.effective=true` means the deadline may be treated as
an active constraint for that historical decision. Inactive, expired/stale,
complete or invalid metadata remains visible for audit but must not be used to
explain urgency or allocation as if it were live. This annotation is applied to
canonical EV telemetry, frozen planner deadline context and archived flex
priority evidence. It changes analysis semantics only and does not alter EV
deadline control behaviour.

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
commissioned. Heating/WW flex-context history and Quooker control/detector
history start when their V0.4 paths are commissioned. Earlier gaps in any of
these evidence families remain missing and must not be backfilled by inference
from current state.

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

`POST /agent/ask` accepts a question and day. The question is used only to
select bounded historical analysis anchors and, when it contains explicit
clock times, to scope the large historical evidence arrays around those times;
it never changes EMS state. The response contains the answer plus bounded
evidence counts/status. Raw model responses and credentials are not persisted.

## Runtime model tuning

The analysis model is configured through the systemd service environment.

- `EMS_AI_MODEL` selects the OpenAI model.
- `EMS_AI_REASONING_EFFORT` selects reasoning effort; the application default is `medium`.
- `EMS_AI_MAX_OUTPUT_TOKENS` limits the combined reasoning and answer output budget; the application default is `1200`.

The deployed analysis service currently uses `medium` reasoning effort with a
4096-token output ceiling. A measured successful request on 2026-10-04 spent
about 198 seconds end-to-end while local evidence construction took about
0.68 seconds, so `high` reasoning was retired as the production default while
latency is observed. These settings affect analysis only and do not grant
control-write authority.

Model-response failures are classified before an empty answer is reported. A
Responses API result with `status=incomplete` and
`incomplete_details.reason=max_output_tokens` is exposed as
`MODEL_INCOMPLETE_MAX_OUTPUT_TOKENS`; content-filter incompleteness,
refusals, explicit response errors and genuinely empty completed responses keep
separate diagnostic codes. On such failures the service writes one bounded JSON
diagnostic event to the systemd journal containing only response ID, response
status/reason and token-count metadata. The user's question, EMS evidence,
model text/refusal text and credentials are never written to that diagnostic
event. Successful model calls also emit one bounded
`EMS_AI_MODEL_RESPONSE_SUCCESS` journal event with response ID, model-call
duration and aggregate token counts. The same privacy boundary applies: no
question, EMS evidence or model answer text is logged.

A PENDING UI job is considered stale only when its age exceeds the stale
threshold **and** no active request in the current analysis-service process owns
that request ID. This prevents a valid long-running model call from being
reclaimed and duplicated after 180 seconds, while still allowing an orphaned
PENDING row left by a process restart or crash to be reclaimed later.

This observability/lifecycle path does not retry the model request and does not
change the output-token limit.
