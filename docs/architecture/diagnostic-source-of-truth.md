# Diagnostic source of truth

**Status:** canonical diagnostic architecture rule  
**Scope:** EMS runtime, control, command input, website publication and future end-to-end chain analysis

## 1. Purpose

This document defines which source is authoritative when diagnosing each EMS layer. Before inspecting data, first identify the layer and its canonical source. Diagnose a chain from source to destination, one boundary at a time.

## 2. Canonical diagnostic sources

### Runtime state

```text
Homey devices → Homey Core / EM2_Public_State → direct Homey→Pi push
 → Pi Status API POST /state/energy
 → /home/jeroen/ems/data/energy-state-v2.json
 → Pi planner/history and private Web Data API
```

The Pi-local state is authoritative for runtime conclusions. Former `docs/data/energy-state-v2.json` GitHub publication was retired in September 2026; it is **not** a current or lagging runtime mirror.

### Control

```text
Pi planner → GET /control/current
 → Homey PI Dynamic Planner Bridge → EM2_Power_Intent
 → device adapter → validation gate → sole actuator → physical device
```

Do not diagnose an actuator before checking intent and Gate evidence.

### Website observability

The private EMS website uses the Pi's read-only `GET /web/*` resources via its Tailscale-only frontend. GitHub Pages serves only a neutral static landing page. Historical `docs/data/` JSON files do not establish current runtime or website state.

### User command input

**Tesla deadline (LIVE since 2026-10-09):**

```text
Private Invoer V2 (desktop or iPhone home-screen web app)
 → Tailscale Caddy POST /web/commands/tesla
 → Pi Status API /commands/tesla (loopback, PIN/idempotency validation)
 → /home/jeroen/ems/data/tesla-deadline-command.json (atomic)
 → derived deadline state → GET /control/current
 → Homey Bridge → Adapter → Gate → sole EV writer → Easee
```

`docs/data/tesla-deadline-command.json` is **not** a Pi command-ingress authority. The old GitHub fetcher was retired; never restart it. The separate EMS settings path still reads a GitHub-backed `ems-settings-command.json` exception and must be diagnosed separately.

## 3. Mandatory diagnostic method

For every chain incident or end-to-end validation:

1. Identify the exact chain and ownership boundaries from canonical architecture documentation.
2. Identify the canonical diagnostic source at every boundary before inspecting values.
3. Walk the chain in order and establish the last known-good boundary and first failing boundary.
4. Do not jump downstream, restart services, change flows, or weaken freshness/safety guards before localizing the failing boundary.
5. Explicitly distinguish runtime state, control state, command-transfer state and website/publication state.
6. Derived/cached artifacts may corroborate a diagnosis but may not override another layer's canonical source.

## 4. Root-cause documentation rule

Chain knowledge discovered during troubleshooting is part of the architecture.

Whenever analysis of an end-to-end chain establishes a root cause, the investigation MUST finish by updating this diagnostic source-of-truth document with the durable information learned from that chain.

Record where applicable:

- verified canonical chain and ownership boundaries;
- authoritative diagnostic source at each relevant boundary;
- observed failure boundary and root cause;
- misleading/non-authoritative artifacts that must not be used for that conclusion;
- shortest safe verification sequence for recurrence;
- architecture/documentation inconsistencies discovered during investigation.

Do not turn this document into a chronological incident log. Record reusable diagnostic knowledge. Incident-specific detail belongs in a dedicated runbook when needed.

A troubleshooting task is not architecturally complete at "root cause found". It is complete only after reusable chain knowledge is captured here and affected component/runbook documentation is aligned.

## 5. Tesla deadline diagnostic sequence (live local ingress)

```text
1. POST /web/commands/tesla through the private Tailscale ingress
   (from Invoer V2 or the native Deadline UI)
   verify PIN validation, server acceptance and requestId
2. /home/jeroen/ems/data/tesla-deadline-command.json
   verify the same requestId, target SoC, deadline and maxA
3. /home/jeroen/ems/data/ev-deadline-shadow-state.json
   verify derived lifecycle, remainingKWh and latestStart
4. /control/current
   verify PI authority, planner/execution status and deadline contract
5. Homey Bridge → EM2_Power_Intent
   verify executor intent and authoritative OFF/1P/3P phase control
6. EV Adapter → Gate → EM2_EV_Actuator_Status
   verify final validation and single writer decision
7. Easee/Tesla physical readback
   verify offered current, phase and delivered power
8. Private /web/commands/current and /web/state/current
   verify presentation only after authoritative runtime checks
```

GitHub command JSON and GitHub Pages are no longer checkpoints in the live Tesla deadline chain.
Desktop Safari and the iPhone home-screen web app are the same private V2 browser
interface; neither is a control authority. Diagnose both from the same Pi command
file onward.

### Historical diagnostic lesson — 2026-09-19 (pre-local-ingress)

A V2 Tesla command for 38% -> 51%, local deadline 10:00 Europe/Amsterdam and max 7 A was correct at the command boundary. GitHub-published `docs/data/energy-state-v2.json` still showed an older deadline and initially appeared to indicate failed ingestion.

Canonical Pi runtime proved ingestion was already correct: `deadline_active=true`, `deadline_at=2026-09-19T08:00:00.000Z`, `deadline_max_a=7`, `remaining_kwh=7.15`, and `need=TESLA_DEADLINE_BLOCKED_NOT_CONNECTED`.

Root cause of the apparent mismatch: a lagging GitHub website-publication artifact was consulted as though it were canonical runtime state.

Reusable rule: never infer current Pi deadline acceptance from historical GitHub publication. Since 2026-10-09, diagnose local API acceptance, the canonical Pi command and derived state, then `/control/current` and Homey/Easee.

### Verified diagnostic lesson — Easee phase authentication

For opportunity charging, a healthy Pi planner or even Gate `PASS` does not prove a physical phase switch succeeded. The canonical downstream boundary is `EM2_EV_Actuator_Status`.

On 2026-10-02, live evidence showed:

```text
Pi /control/current     allowed=true, PV_OPPORTUNITY
Homey Bridge            authoritative 1P request
EV Adapter              valid
EV Gate                 PASS
EV actuator             FAILED: Easee authentication
Easee                    remained paused / previous phase
```

The failure was caused by the writer's separately provisioned Easee Cloud session, not by the Homey Easee app session and not by P1/planner logic. Re-running `services/pi/commissioning/bootstrap_easee_homey_tokens.py` restored the private rotating token pair; the next writer execution reached `STABLE`, `confirmedMode=1P` and physical charging.

Reusable shortest check:

```text
1. /control/current -> realtime.ev.allowed / phase policy
2. EM2_Power_Intent -> authoritative phase mode/A
3. EV Adapter/Gate -> requested_A and Gate PASS
4. EM2_EV_Actuator_Status -> reason/stage/authAlert
5. Easee live state -> confirmed phase/current/power
```

A terminal writer auth failure is a trustworthy command-boundary signal. Writer v0.4.5 therefore keeps fail-closed control behavior and emits a deduplicated operational alert. A successfully auto-refreshed first 401 must not alert.

### Verified diagnostic lesson — planner opportunity versus realtime EV stop

A quarter-hour planner slot marked `Tesla RUN / OPPORTUNITY` proves strategic
permission/allocation, not continuous physical charging. The production Homey
Bridge v1.5.7 remains the realtime executor inside the Pi envelope and can emit
`OFF/IDLE` when its rolling available-power phase policy requires it.

For a historical EV pause, inspect the recorded Power Intent reasons before
attributing the pause to forecast error, Gate failure or actuator failure.
`ev_control_events.raw_json` already retains this evidence. The EMS AI reader
must project at least `intentReason`, `realtimePhaseReason` and
`realtimeCurrentReason`, with bounded rolling-power context when present.

The 2026-10-04 12:45–13:00 event established the reusable pattern:
the quarter-hour planner retained EV opportunity, while the realtime controller
temporarily produced IDLE during a rapidly changing PV interval and later
re-entered charging. If the stored realtime reason is present, calling the
control cause “unknown” is a diagnostic error.



## 6. Private V2 web-data diagnostic sequence

The private Pi-hosted V2 read path is:

```text
canonical Pi runtime JSON
 -> localhost Web Data API
 -> Caddy same-origin /web/*
 -> V2 state adapter
 -> renderer
```

For a V2 page that loads but shows unavailable data, verify the chain in that order. A successful direct API response does not prove the browser request is accepted.

The Web Data API intentionally rejects query strings. V2 adapters therefore MUST use the stable resource path with browser `cache: "no-store"`; they MUST NOT append cache-busting query parameters. Caddy and the API already return no-store semantics where applicable.

Shortest safe recurrence check:

```text
1. curl http://127.0.0.1:3200/web/<resource>
2. curl http://192.168.1.42/web/<resource>
3. inspect the deployed adapter SOURCE
4. request the exact URL constructed by that adapter
```

If step 2 succeeds but step 4 returns HTTP 400, inspect URL construction before changing API, Caddy, renderer or runtime state.

### iPhone home-screen web app

The iPhone home-screen experience is the same private V2 website described above:
`http://100.127.130.0/` redirects to `/live/`, and all data/command traffic stays on
the existing Tailscale-only Caddy `/web/*` boundary. There is no separate native
Mobile V1 API to diagnose.

## 7. Private V2 command-Worker diagnostic sequence

The authenticated Tesla/EMS command path begins:

```text
private V2 browser
 -> same-origin static Worker config
 -> browser CORS preflight (OPTIONS)
 -> authenticated Cloudflare Worker POST
 -> GitHub command JSON
 -> Homey adapter/Core
 -> canonical Pi runtime state
```

If the config loads and the PIN prompt appears but browser submission reports a generic network/load failure, test the Worker boundary before inspecting GitHub, Homey or Pi:

```text
1. GET the Worker URL only to prove network reachability; HTTP 405 is expected for a POST/OPTIONS-only Worker.
2. Send OPTIONS with the exact browser Origin, requested POST method and requested headers.
3. Require HTTP 2xx and Access-Control-Allow-Origin equal to that exact trusted origin.
4. Only then perform an authenticated POST/write test.
```

A 403 `origin_not_allowed` with `Access-Control-Allow-Origin: null` proves the first failing boundary is the Worker CORS allowlist; it does not indicate a Worker outage and no command write has occurred. Fix the explicit trusted-origin allowlist; do not weaken it to `*`.

The canonical Worker source is `apps/cloudflare/`. Cloudflare Git deployment must watch only `apps/cloudflare/**`; generated runtime/publication commits elsewhere in the repository are not Worker deployment inputs.

## 8. Related canonical architecture

- `docs/architecture/CURRENT-EMS-STATE.md`
- `docs/architecture/homey-pi-runtime-dataflow.md`
- `docs/architecture/runtime-publication-separation.md`
- `docs/architecture/tesla-deadline-end-to-end.md`
- `docs/architecture/ems-software-architecture-live.md`
