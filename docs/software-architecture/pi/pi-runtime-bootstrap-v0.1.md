# Pi EMS Runtime Bootstrap v0.1

Status: IMPLEMENTATION SCAFFOLD / SHADOW-ONLY — synced 2026-08-30

## Software stack

- Raspberry Pi OS Lite 64-bit host
- Docker Engine + Compose
- Python 3.12 EMS runtime
- PostgreSQL 16 for durable EMS history/state records
- Mosquitto 2 for event transport
- Prometheus client for runtime metrics
- Read-only FastAPI Management API bound to localhost

## Hardware/storage baseline

- Raspberry Pi 5, 8 GB
- official 27 W PSU
- official Active Cooler
- Geekworm X1001 NVMe adapter
- PNY CS1030 500 GB NVMe — **primary 24/7 EMS runtime, PostgreSQL database and history storage**
- Geekworm P579 case
- SanDisk Extreme 128 GB microSDXC UHS-I A2/U3/V30, Amazon ASIN `B09X7BK27V` — **installation/bootstrap/recovery medium only**

The microSD is not the production database/history target. The installation procedure must end with the EMS runtime and persistent `/opt/ems` data on the 500 GB NVMe. Recovery media remains independently bootable/replaceable.

## Process boundaries

`ems-core` owns Central State and deterministic EMS domain logic. `homey-gateway` code is the sole Homey I/O boundary. Victron will receive its own gateway. Publisher remains publication-only.

The bootstrap intentionally does not split Core, Planner, Decisions, Power Intent, adapters and gates into separate network services. They remain one deployable Python application until operational evidence justifies separation.

## 2026-08-30 architecture sync

The Pi bootstrap now follows today's low-load Homey baseline:

- Core reference is v0.11a Targeted Device Reads; broad collection scans are not an acceptable Pi commissioning pattern.
- `Core Snapshot Aggregator v0.2 SHADOW NO-QUOOKER` is the preferred Homey→Pi commissioning boundary, subject to runtime validation.
- Canonical snapshot variable: `EM2_CORE_INPUT_V0.1`; ownership lease: `EM2_CORE_INPUT_LEASE_V0.1`.
- Snapshot consumption must be read-once/normalize-once/fan-out-locally; the Pi must not independently reproduce Homey-side fan-in on every cycle.
- Quooker is deliberately outside the Core/Central State critical path and outside this initial Pi migration slice.
- Publisher v1.0.11 SCHEDULED LOW-LOAD is the publication reference; publication must remain downstream and must never wake the control chain.
- Exact active Homey contracts still requiring capture/closure include Publisher v1.0.11, WW Power v0.2, WW Gate v0.2 and WW Actuator v0.9.
- No Pi LIVE ownership transfer is authorized by this scaffold.

## Safety defaults

- `EMS_MODE=SHADOW` is the default.
- The v0.1 application refuses any other mode.
- The Homey gateway implements reads only; no actuator-write API exists.
- Homey 429 raises a dedicated rate-limit condition and must not trigger an immediate retry loop.
- Missing/stale P1 state blocks positive flexible-load control.
- External I/O is prohibited from domain modules.
- No broad Homey discovery/collection scans in steady state.
- No Quooker dependency in Core/Central State commissioning.
- No physical device write from the Management API.

## Bootstrap layout

```text
src/pi/
├── app.py
├── config.py
├── management_api.py
├── health.py
├── publisher.py
├── replay_runner.py
├── pyproject.toml
├── .env.example
├── ems/
│   ├── models.py
│   ├── state.py
│   ├── replay.py
│   ├── ev_semantics.py
│   └── ww_semantics.py
├── gateways/
│   ├── homey.py
│   └── mock_homey.py
├── migrations/
│   └── 001_bootstrap.sql
└── tests/
    ├── fixtures/
    └── test_*.py

docker/pi/
├── Dockerfile
├── docker-compose.yml
└── mosquitto.conf

install/pi-ems-bootstrap-v0.1/
├── README-FIRST.md
├── MANIFEST.md
├── RESTORE.md
├── install.sh
├── verify.sh
├── config/
├── docker/
├── migrations/
└── system/
```

## Implemented preparation baseline

- Central State schema/model and stale/missing fail-closed handling.
- Read-only Homey gateway scaffold with dedicated 429 handling.
- PostgreSQL bootstrap migration for observations, snapshots/decisions/intents/gates/shadow comparisons/health.
- Deterministic replay runner and EV/WW semantic fixtures/tests.
- Publisher SHADOW projection foundation.
- Read-only Management API with bearer authentication for `/v1/*`, minimal `/healthz` and metrics; localhost binding only.
- Hardened installer package with UFW/security setup, backups, restore documentation and image-lock capture.
- Daily local PostgreSQL/config backup at 03:17 with 14-day retention baseline.
- Container hardening baseline: read-only where applicable, no-new-privileges, dropped capabilities and bounded logging.

These are source-level preparations. Runtime execution on the physical Pi and full CI/replay PASS must not be claimed until actually executed and recorded.

## Current non-goals

No steady-state Homey polling is enabled by the Pi application yet. No Cerbo connection exists yet. No LIVE Publisher ownership transfer exists yet. No device write is possible from Pi. Homey remains the operational control owner until deterministic parity and explicit promotion gates pass.

## Next implementation slice

1. Add a Pi parser and fixtures for `EM2_CORE_INPUT_V0.1`, including `revision`, `generatedAt`, freshness and missing/stale handling.
2. Runtime-validate Aggregator v0.2 NO-QUOOKER with minimal targeted Homey reads; stop immediately on 429 and do not brute-force probe.
3. Capture exact Publisher v1.0.11 and replace provisional Publisher replay assumptions with the active contract.
4. Capture exact WW Power v0.2, WW Gate v0.2 and WW Actuator v0.9 contracts and update replay coverage.
5. Establish the Pi commissioning Homey read budget and expected calls/hour before real polling is enabled.
6. Add representative runtime fixtures: idle/night, PV production, EV connected-paused, EV charging, WW OFF/ON. Quooker is excluded from this slice.
7. Validate the installer on the physical Pi: boot from the SanDisk recovery/bootstrap medium, install/migrate the runtime to NVMe, reboot from/with NVMe as primary persistent storage, run `verify.sh`, and record evidence.
8. Only after the above: begin Pi SHADOW Homey comparison. No LIVE ownership change.
