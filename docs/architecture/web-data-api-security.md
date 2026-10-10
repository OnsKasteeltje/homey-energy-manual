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

## 15. Current State resource

The Live V2 migration uses:

```text
/home/jeroen/ems/data/energy-state-v2.json
                 |
                 v
allowlisted Web Data API projection
                 |
                 v
GET /web/state/current
                 |
                 v
Frontend V2 / Live
```

Schema: `EMS_WEB_STATE_CURRENT_V1`. Only fields consumed by the Live V2 state adapter are exposed. The API does not serialize the complete canonical runtime document and does not derive EMS policy. GitHub `docs/data/energy-state-v2.json` is not a runtime fallback for the private V2 site.

## 15.1 Current command-state resource

Invoer V2 uses a separate read-only command-state projection:

```text
docs/data/tesla-deadline-command.json + docs/data/ems-settings-command.json
                 |
                 v
allowlisted Web Data API projection
                 |
                 v
GET /web/commands/current
                 |
                 v
Frontend V2 / Invoer
```

Schema: `EMS_WEB_COMMANDS_CURRENT_V1`. This endpoint exposes only the last accepted command fields required by Invoer. It does not write commands, does not convert command state into runtime state, and does not alter the existing authenticated command route. Missing or malformed command sources fail closed with the standard generic resource-unavailable response.

## 15.2 Heating Preheat shadow resource

PV Flex may consume the current read-only Heating Preheat commissioning state through:

```text
/home/jeroen/ems/data/heating-preheat-shadow-v0.3.json
                 |
                 v
allowlisted Web Data API projection
                 |
                 v
GET /web/planner/heating-preheat-shadow
                 |
                 v
Frontend V2 / PV Flex
```

Schema: `EMS_WEB_HEATING_PREHEAT_SHADOW_V1`. The endpoint accepts only the canonical `EMS_HEATING_PREHEAT_SHADOW_V0.3` source with `mode=READ_ONLY`, `controlMode=SHADOW`, `controlWrites=false` and Honeywell baseline authority. It exposes only the room/window/guard fields required for commissioning; the CV observation is named `cvGuard.cvActive`. For diagnostics the allowlist also exposes `observedAt`, the single guard `ageSeconds`, and `sourceLastUpdated`. The guard age retains the existing Quatt current artifact freshness semantics; `observedAt` identifies the successful fetch that produced the value and `sourceLastUpdated` is provenance/last-change information only. The Web Data API does not calculate eligibility, CV-assist policy, PV priority or step progression. Missing or invalid source data affects only this presentation resource and has zero control impact.

## 15.3 Flex Priority shadow resource

PV Flex may also consume the current cross-domain Heating ↔ EV priority decision through:

```text
/home/jeroen/ems/data/flex-priority-shadow-v0.1.json
                 |
                 v
allowlisted Web Data API projection
                 |
                 v
GET /web/planner/flex-priority-shadow
                 |
                 v
Frontend V2 / PV Flex
```

Schema: `EMS_WEB_FLEX_PRIORITY_SHADOW_V1`. The canonical source is `EMS_PI_FLEX_PRIORITY_SHADOW_V0.1` and is accepted only when it is `READ_ONLY / SHADOW`, `controlWrites=false`, `powerReservationW=0` and realtime opportunity authority remains `P1`. The API exposes only the chosen priority owner, Heating shadow-grant state, EV role/urgency and closing-time context needed for commissioning. It never computes priority itself and cannot authorize a physical write.

## 15.4 Heating Preheat V0.4 progression shadow resource

PV Flex may consume the stateful progression commissioning layer through:

```text
/home/jeroen/ems/data/heating-preheat-progression-shadow-v0.4.json
                 |
                 v
allowlisted Web Data API projection
                 |
                 v
GET /web/planner/heating-preheat-progression-shadow
/web/heating/temperature-history
                 |
                 v
Frontend V2 / PV Flex
```

Schema: `EMS_WEB_HEATING_PREHEAT_PROGRESSION_V1`. The source must be canonical `EMS_HEATING_PREHEAT_PROGRESSION_SHADOW_V0.4`, `READ_ONLY / SHADOW`, `controlWrites=false`, `physicalWriteAllowed=false`, Honeywell baseline authority, V0.3 eligibility authority and Flex Priority V0.1 allocation authority. The API rejects any room state reporting a physical write, any step bound other than `0.5 C`, intentional grid import, or any rollback mode other than `NOT_DEFINED_SHADOW_ONLY`.

The endpoint is presentation-only. It exposes progression state, active/next shadow target, measured-step completion, transition metadata and allowlisted closed `stepHistory` intervals for the four scoped rooms. The interval history is bounded by the producer and carries only opportunity id, target, start/end, outcome and reason. It does not calculate progression, reconstruct missing historical intervals, planner grants, Honeywell targets, CV policy or device commands.

## 15.5 Heating room-temperature history resource

Frontend V2 / Verwarming may read the canonical six-hour room-temperature history through:

```text
ems-history.sqlite / measurements_15m
  honeywell_<room> / room_temperature_c
                 |
                 v
allowlisted Web Data API projection
                 |
                 v
GET /web/heating/temperature-history
                 |
                 v
Frontend V2 / Verwarming
```

Schema: `EMS_WEB_HEATING_TEMPERATURE_HISTORY_V1`. The resource is presentation-only and exposes only the four scoped rooms (`woonkamer`, `eetkamer`, `keuken`, `serre`) and canonical `room_temperature_c` 15-minute observations from the preceding six hours. Only `complete` and `partial` measurement buckets are presented; held/other quality states are not promoted to measured truth. The resource performs no interpolation and contains no planner, PV, CV or Honeywell-control policy.

The Verwarming page joins this history only for presentation with the existing Honeywell baseline schedule, V0.3 current preheat eligibility/window and V0.4 current progression state. It must not invent historical V0.3/V0.4 events from a current snapshot. A current active shadow target may be drawn only from its recorded `activeStepStartedAt` through the current observation time.

## 16. Planned resource families

This first endpoint establishes the boundary for the entire website. Expected resource families include:

```text
/web/state/current
/web/planner/current
/web/planner/heating-preheat-shadow
/web/planner/heating-preheat-progression-shadow
/web/planner/flex-priority-shadow
/web/history/day
/web/history/daily
/web/status/ev
/web/ww/seasonal-advice
```

Exact schemas are defined independently before each cutover. No resource is migrated merely because this list exists.

## 17. Migration and rollback

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

## 18. Security validation gate

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

## 19. Definition of Done

A Web Data API change is complete only when:

```text
IMPLEMENTATION PASS
SECURITY VALIDATION PASS
RUNTIME VALIDATION PASS
GITHUB SOURCE SYNC PASS
ARCHITECTURE DOCUMENTATION PASS
```

Security is therefore a release gate, not a post-implementation hardening task.


## Unified tailnet-only V2 website (PR #213 LIVE, 2026-10-09)

The deployed EV Command Ingress V1.1 cutover standardizes **all** website
access, not just writes, on the single Tailscale IP and same origin:
`http://100.127.130.0/`. Caddy listens only on the Pi's Tailscale
interface. A trusted home LAN client does not get a separate website route.
Mac, iPhone and future native app use this URL after joining the authorized
tailnet. Website requests, including PIN-bearing POSTs, travel inside the
encrypted Tailscale peer tunnel; the HTTP scheme does not imply an HTTPS
secure browser context. Keep the one shared origin if HTTPS is later added.

The read-only Web Data API still binds to localhost `127.0.0.1:3200`.
The Pi status/control API and Homey LAN control path remain unchanged,
and the command handler refuses non-loopback direct callers. Never open a
public listener, port forwarding, Funnel, or second LAN browser entrypoint.
Pi preflight and runtime listener checks confirmed the single tailnet-only Caddy binding. Historical LAN-plus-tailnet rules above describe the previous deployment and are superseded for the V2 frontend. Mobile client functionality and a successful new authenticated deadline to physical Easee charging remain separate outstanding runtime validations.


## Dynamic Planner V1 observability projection (2026-10-10)

The read-only `GET /web/planner/current` endpoint exposes an allowlisted 96 × 15-minute
projection of the canonical `dynamic-shadow-plan.json`, schema
`EMS_WEB_DYNAMIC_PLAN_V1`: original V1 PV forecast, planner confidence,
EV/WW planned watts, projected grid import/export and per-slot allocation reasons.
The source, validity and monotonic axis are checked before serving; malformed
or expired plans are unavailable rather than treated as current.

This is a *projection of the actual Dynamic Pi Planner decision*, not a
second PV forecast, an optimization or a physical-control path. The
`/web/planner/pv-forecast` V2 endpoint is temporarily retained for rollback
and historical research, not consumed by the Planner frontend. No new writer,
Homey publisher or independent planning authority is introduced.

## Read-only archived Planner V1 evaluation resource

`GET /web/analysis/planner/day/YYYY-MM-DD` exposes the canonical V1 forecast saved at least 12 hours before each target slot and, independently, the latest still-valid EV/WW allocation saved before that slot. Only allowlisted values and their generation times leave `planner-history.sqlite`; the original V2 forecast archive remains available for rollback but is never silently used as V1. This API is presentation-only and does not reconstruct new decisions.
