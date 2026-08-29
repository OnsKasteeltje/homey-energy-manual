# Pi EMS Runtime Bootstrap v0.1

Status: IMPLEMENTATION SCAFFOLD / SHADOW-ONLY

## Software stack

- Raspberry Pi OS Lite 64-bit host
- Docker Engine + Compose
- Python 3.12 EMS runtime
- PostgreSQL 16 for durable EMS history/state records
- Mosquitto 2 for event transport
- Prometheus client dependency reserved for runtime metrics

## Process boundaries

`ems-core` owns Central State and deterministic EMS domain logic. `homey-gateway` code is the sole Homey I/O boundary. Victron will receive its own gateway. Publisher remains publication-only.

The bootstrap intentionally does not split Core, Planner, Decisions, Power Intent, adapters and gates into separate network services. They remain one deployable Python application until operational evidence justifies separation.

## Safety defaults

- `EMS_MODE=SHADOW` is the default.
- The v0.1 application refuses any other mode.
- The Homey gateway implements reads only; no actuator-write API exists.
- Homey 429 raises a dedicated rate-limit condition and must not trigger an immediate retry loop.
- Missing/stale P1 state blocks positive flexible-load control.
- External I/O is prohibited from domain modules.

## Bootstrap layout

```text
src/pi/
├── app.py
├── pyproject.toml
├── .env.example
├── ems/
│   ├── models.py
│   └── state.py
├── gateways/
│   └── homey.py
└── tests/
    └── test_state.py

docker/pi/
├── Dockerfile
├── docker-compose.yml
└── mosquitto.conf
```

## Current non-goals

No Homey polling is started by the application yet. No Cerbo connection exists yet. No GitHub Publisher executes yet. No device write is possible. Database schema/migrations and production MQTT authentication are subsequent bootstrap steps.

## Next implementation slice

1. Add configuration model and service health endpoint/metrics.
2. Add PostgreSQL migrations for observations, decisions, intents, gate results and shadow comparisons.
3. Implement a mock/fixture Homey Gateway first.
4. Add exact Homey read mapping only after the relevant source contracts are captured and Homey is healthy enough for controlled validation.
5. Add Publisher SHADOW output without production overwrite.
