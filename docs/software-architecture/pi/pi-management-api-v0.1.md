# Pi Management API v0.1

Status: PREPARATION / SHADOW ONLY

## Purpose

Provide a deliberately narrow observability boundary for the Raspberry Pi EMS. It is intended for future secure tooling/ChatGPT access without granting direct shell access, Docker control or actuator control.

## Safety model

- API starts only when `EMS_MODE=SHADOW`.
- No POST, PUT, PATCH or DELETE routes exist in v0.1.
- `write_capability=false` and `control_operations=false` are explicit status fields.
- The container does not receive the Docker socket.
- The container is read-only, drops all Linux capabilities and uses `no-new-privileges`.
- The host mapping is `127.0.0.1:8088:8080`: it is not reachable directly from the LAN or Internet.
- All `/v1/*` endpoints require a bearer token generated during bootstrap.
- `/healthz` is the only unauthenticated endpoint and returns only minimal liveness/safety data.
- Prometheus metrics are mounted at `/metrics`; because the host port is localhost-only they are not LAN exposed in v0.1.
- No Homey, Easee, boiler or Victron actuator operation is exposed.

## Read-only endpoints

- `GET /healthz` — local liveness, mode and write capability.
- `GET /v1/status` — release, SHADOW mode, DB health and integration-configured flags.
- `GET /v1/state` — latest persisted Central State snapshot.
- `GET /v1/shadow-comparisons?limit=N` — latest Homey/Pi comparison records.
- `GET /v1/system-health?limit=N` — persisted component health history.
- `GET /v1/power-intents?limit=N` — persisted Power Intent history.
- `GET /v1/gate-results?limit=N` — persisted gate outcomes.
- `GET /metrics` — Prometheus process/runtime metrics.

## Access path

The API is intentionally localhost-only. A future ChatGPT integration must use a separately designed authenticated outbound tunnel, VPN/overlay or connector that terminates on the Pi and reaches `127.0.0.1:8088`. Router port-forwarding to this API is prohibited by design.

GitHub remains the software control plane. The Management API is for inspection/diagnostics, not for editing source files or deploying arbitrary code.

## Future phases

A later version may add tightly scoped administrative commands, but only after a separate threat/safety review. Any future command capable of influencing physical equipment must pass through the same EMS gates, stale checks, limits, idempotency and ownership rules as autonomous control. Generic shell, Docker socket and unrestricted actuator endpoints remain out of scope.
