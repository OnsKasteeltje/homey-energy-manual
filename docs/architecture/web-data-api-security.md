# EMS Web Data API — Security and interface contract

**Status:** Canonical private target architecture / mandatory security baseline  
**Date:** 2026-09-19  
**Scope:** Entire Frontend V2 read-only operational-data interface  
**Governance:** `ems-architecture-governance.md`, `architectuur-guardrails.md`, `repository-structure.md`, `runtime-publication-separation.md`, `ems-frontend-v2-architecture.md`

## 1. Purpose

The Web Data API is the single target read-only operational-data boundary for the entire EMS website. Warm-water Seasonal Advice is the first vertical slice, not a separate API design.

Target:

```text
canonical Pi runtime/history/planner data
                  |
                  v
       EMS Web Data API
       services/pi/api/web-data/
                  |
        secured HTTPS boundary
                  |
                  v
           Frontend V2
 Live / Invoer / Historie / Planner / Groepen & fasen
```

GitHub remains canonical for source/configuration/documentation. It is not the target runtime telemetry transport.

## 2. Hard ownership boundary

- Pi owns runtime state, planning, history and the Seasonal Advisor.
- Homey owns realtime state, safety and execution.
- Web Data API owns read-only serialization/exposure only.
- Frontend owns presentation only for read resources.
- Explicit user commands use a separate authenticated command boundary.
- The Web Data API MUST NOT contain EMS optimization, advice calculation, actuator policy or physical writes.
- Failure or compromise of the Web Data API MUST NOT be able to create a Homey/device write path.

## 3. Repository placement

New production implementation belongs under:

```text
services/pi/api/web-data/
```

Deployment definitions belong under:

```text
deploy/systemd/
```

Tests belong under the matching canonical test boundary. Production implementation MUST NOT be introduced under `docs/`, `src/pi/` or generated-data paths.

Every material change remains subject to **Touch it, place it correctly** and `tools/validation/repository_structure_gate.sh`.

## 4. Private access boundary

Frontend V2 and the Web Data API are private household services. They MUST NOT be made publicly reachable from the internet.

Target access paths:

```text
local device on trusted home LAN
          |
          v
   Pi-hosted Frontend V2
          |
          v
 localhost Web Data API

remote trusted device
          |
          | Tailscale tailnet
          v
   Pi-hosted Frontend V2
          |
          v
 localhost Web Data API
```

The API origin remains bound to localhost by default. The preferred remote-access boundary is Tailscale; Tailscale Funnel is forbidden. Router port-forwarding, a public listener, Cloudflare Tunnel/public ingress, or any other public internet exposure is outside the current architecture.

The V2 website itself is hosted on the Pi. GitHub remains source/configuration/documentation and transitional publication infrastructure during migration; GitHub Pages is not the target host for private V2 runtime operation.

The current private ingress design is deliberately interface-specific:

- Caddy serves V2 on wired LAN address `192.168.1.42` only;
- the Wi-Fi address `192.168.1.45` is not a V2 ingress;
- wildcard binding (`0.0.0.0`) is forbidden for the V2 web ingress;
- Docker interfaces are not V2 ingress;
- `/web/*` is reverse-proxied same-origin to `127.0.0.1:3200`;
- Tailscale remote access is a separate private ingress and MUST NOT use Funnel.

The LAN addresses are router-reserved for the Pi. A future address/interface change requires deliberate deployment and architecture review rather than widening the listener.

## 5. Transport and authentication requirements

1. Remote access outside the trusted home LAN MUST traverse the private Tailscale tailnet.
2. Tailscale access uses least privilege and only authorized tailnet identities/devices.
3. The Web Data API remains localhost-scoped unless a later documented design explicitly changes that boundary.
4. No secrets, credentials, API keys or tokens are embedded in Frontend V2 JavaScript or committed to GitHub.
5. No router port-forward, public DNS ingress, Tailscale Funnel or other public exposure is permitted.
6. Management/debug endpoints are not exposed beyond the private management boundary.
7. Where HTTPS is used for remote browser access, termination is provided by the approved private ingress (for example Tailscale Serve), not by exposing the API directly.
8. Access failures fail closed.

## 6. HTTP surface

The Web Data API is read-only.

- Resource endpoints allow `GET`.
- `HEAD` may be supported deliberately where useful.
- Cross-origin browser preflight may support `OPTIONS` only where required.
- `POST`, `PUT`, `PATCH`, `DELETE` and unsupported methods return `405 Method Not Allowed`.
- No generic filesystem endpoint exists.
- No request parameter may become a filesystem path.
- No shell/subprocess execution is reachable from a web-data request.
- Resources are explicitly allowlisted in code.
- Query parameters are explicitly defined, typed, bounded and rejected when unknown/invalid where practical.

User commands are outside this API.

## 7. Browser origin policy

The preferred deployment is same-origin: the Pi-hosted V2 frontend reaches the Web Data API through the same private web origin/reverse-proxy boundary. In that design no browser CORS permission is required.

If a temporary migration step requires cross-origin access, CORS MUST be minimal and explicit:

- never use `Access-Control-Allow-Origin: *` for EMS operational data;
- allow only the exact private V2 origin(s) required;
- do not blindly reflect arbitrary `Origin` values;
- CORS is a browser control, not an authentication mechanism;
- remove temporary CORS support when same-origin migration is complete.

## 8. Response minimization and schemas

Every endpoint has a versioned response schema and an explicit response-field allowlist.

The API exposes only fields required by the consuming page. It MUST NOT serialize arbitrary source JSON wholesale merely because the source file contains it.

Responses retain enough provenance for safe presentation:

- schema/version;
- generated/source timestamp where available;
- freshness/status semantics where relevant;
- explicitly documented domain fields.

Internal filesystem paths, stack traces, secrets, tokens, Homey credentials and unrelated diagnostic internals are never returned.

Unknown/null remains unknown/null unless the canonical source contract defines another semantic.

## 9. Freshness and failure semantics

Freshness is part of the resource contract, not silently inferred by a renderer.

- The canonical producer remains responsible for domain state/advice.
- The Web Data API may validate source existence/schema/timestamps and expose a documented availability/freshness state.
- It MUST NOT recalculate domain advice or optimization.
- Missing, malformed or unacceptable source data fails closed for that presentation resource.
- API failure does not affect planner, state ingest, `/control/current`, Homey execution or actuators.
- Error responses are generic and do not expose implementation details.

## 10. Abuse and resource protection

The private web boundary and origin use bounded resource consumption.

- Rate limiting may be applied at the private ingress where useful; bounded origin behavior remains mandatory.
- Request size, parameter ranges and history windows are bounded.
- No unbounded history/export query is permitted.
- Expensive resources must have explicit maximum ranges and/or pagination.
- Timeouts are finite.
- The API must not permit user-selected arbitrary SQL, filenames, commands or upstream URLs.
- Repeated invalid/authentication requests are observable without logging secrets.

## 11. Security headers and caching

JSON responses explicitly use `Content-Type: application/json` and `X-Content-Type-Options: nosniff`.

Protected/user-specific responses default to conservative caching (`Cache-Control: no-store`) unless a resource is deliberately classified safe for bounded shared caching.

The private HTTPS ingress owns HSTS where HTTPS is enabled. Additional browser security headers may be applied centrally where appropriate.

## 12. Logging and observability

Security-relevant events are observable while minimizing sensitive data.

Log:
- timestamp;
- endpoint/resource;
- response class/status;
- validation/auth rejection category where available at that layer;
- latency sufficient for operational diagnosis.

Do not log:
- credentials/tokens;
- authorization cookies;
- secrets;
- full sensitive request headers.

Logs are not a second runtime state source.

## 13. API inventory and versioning

All public web-data resources are inventoried in canonical architecture documentation. New endpoints require:

1. named canonical source;
2. owner;
3. response schema/version;
4. consuming frontend page;
5. freshness/failure semantics;
6. security classification;
7. bounded query contract;
8. tests.

Breaking contract changes require a deliberate version transition; silent incompatible response changes are forbidden.

## 14. Initial resource — WW Seasonal Advice

First vertical slice:

```text
/home/jeroen/ems/data/ww-seasonal-advisor.json
                 |
                 v
Web Data API read adapter
                 |
                 v
GET /web/ww/seasonal-advice
                 |
                 v
Frontend V2 / Invoer
```

The resource is a projection of canonical advisor output, not a copy of its full runtime JSON.

Minimum domain fields:

- API schema/version;
- source `generatedAt`;
- advisor `status`;
- advisor `advice`;
- `currentMode`;
- confirmation state only if required by the UI contract.

Frontend presentation maps canonical advisor output to exactly:

- `Advies: blijf op CV/Boiler`;
- `Advies: schakel naar CV/Boiler`;
- `Advies: nog niet beschikbaar`.

The frontend MUST NOT calculate the economic recommendation itself.

## 15. Planned resource families

This first endpoint establishes the boundary for the entire website. Expected resource families include:

```text
/web/state/current
/web/planner/current
/web/history/day
/web/history/daily
/web/status/ev
/web/ww/seasonal-advice
```

Exact schemas are defined independently before each cutover. No resource is migrated merely because this list exists.

## 16. Migration and rollback

Each existing GitHub runtime publication migrates independently:

```text
inventory
 -> define versioned API contract
 -> implement read-only resource
 -> secure private route
 -> parallel comparison
 -> switch one frontend consumer
 -> validate values/freshness/failure behavior
 -> monitor
 -> retire corresponding GitHub runtime publication only after rollback window
```

No existing publisher or website consumer is disabled as part of creating the API foundation.

## 17. Security validation gate

Before any Web Data API resource is considered production-ready, prove at minimum:

- no direct public Pi port, router port-forward, Funnel or other public ingress;
- API origin remains localhost-scoped;
- local V2 access is limited to the trusted LAN;
- remote V2 access is limited to authorized Tailscale clients;
- unauthorized/non-tailnet remote access is unavailable;
- unsupported write methods rejected;
- same-origin browser access is preferred; any temporary CORS origin behavior is exact and validated;
- no secrets in frontend/repository/URLs/responses/logs;
- response field allowlist validated;
- malformed/stale source fails safely;
- request/range limits validated;
- API outage has zero control impact;
- repository structure gate PASS.

## 18. Definition of Done

A Web Data API change is complete only when:

```text
IMPLEMENTATION PASS
SECURITY VALIDATION PASS
RUNTIME VALIDATION PASS
GITHUB SOURCE SYNC PASS
ARCHITECTURE DOCUMENTATION PASS
```

Security is therefore a release gate, not a post-implementation hardening task.
