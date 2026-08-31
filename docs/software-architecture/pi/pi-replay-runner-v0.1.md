# Pi EMS Integrated Replay Runner v0.1

Status: OFFLINE / SHADOW TOOLING

The replay runner is the standard deterministic regression boundary for Pi EMS migration. It performs no Homey, Victron, MQTT, database or GitHub publication I/O.

## Input

One JSON fixture contains:

- canonical device/state observations;
- replay timestamp;
- EV semantic decision input;
- Publisher revision/timing input;
- expected outputs.

## Execution

From `src/pi`:

```bash
python replay_runner.py tests/fixtures/replay_ev_deadline_publish.json
```

Optional machine-readable report file:

```bash
python replay_runner.py tests/fixtures/replay_ev_deadline_publish.json --output replay-report.json
```

Exit code `0` means all declared expectations passed. Exit code `1` means at least one declared expectation failed.

## Report

Schema: `PI_EMS_REPLAY_REPORT_V0.1`.

The report contains:

- fixture ID;
- deterministic replay clock;
- overall `PASS` / `FAIL`;
- individual comparison checks;
- actual Core projection;
- actual EV semantic output;
- actual Publisher decision and, when due, publication payload.

## Safety boundary

A replay PASS proves only deterministic equivalence against the fixture expectations. It does NOT authorize LIVE writes or ownership transfer.

Promotion remains:

```text
OFFLINE REPLAY PASS
        ↓
PI SHADOW
        ↓
HOMEY ↔ PI COMPARISON
        ↓
OBSERVATION WINDOW
        ↓
EXPLICIT PROMOTION GATE
        ↓
OWNERSHIP TRANSFER
```

The runner must remain free of external I/O so it can be used safely when Homey is throttled or unavailable.

## Next evolution

- ingest captured Homey snapshots without hand conversion;
- store replay reports in `shadow_comparisons`;
- compare exact semantic fields and numeric fields with named tolerances;
- add WW Planner/Power Intent/Adapter/Gate stages;
- batch replay historical scenarios as a regression suite.
