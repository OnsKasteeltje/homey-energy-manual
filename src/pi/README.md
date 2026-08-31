# Pi EMS Runtime

Status: bootstrap scaffold; SHADOW only.

## Runtime boundaries

- `ems/`: deterministic domain logic and central state.
- `gateways/`: all external I/O. Domain code MUST NOT call Homey, Victron or GitHub directly.
- `publisher/`: publication-only output path.
- No positive physical device writes are enabled in v0.1.

## Initial process model

One Python application owns Central State, Core, Planner, Decisions, Power Intent, adapters and gates. External gateways remain explicit boundaries. This avoids premature microservice fan-out while keeping future separation possible.

## Local start

```bash
cp .env.example .env
docker compose -f docker/pi/docker-compose.yml up --build
```

The bootstrap starts in `EMS_MODE=SHADOW` and refuses LIVE mode unless a later explicitly implemented promotion guard allows it.
