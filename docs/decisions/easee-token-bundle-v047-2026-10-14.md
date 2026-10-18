# Easee rotating-token recovery — v0.4.7 LIVE (14–17 October 2026)

**Status: DEPLOYED AND OPERATIONALLY ACCEPTED, 17 October 2026.**
The production physical writer is Homey Advanced Flow
`fea23193-a03f-49dd-9780-7e72ee48747d`, version
`EV Power v0.4.7 ATOMIC-TOKENS [LIVE]`.
This document retains the design limits and records the observed
production acceptance of
[PR #276](https://github.com/OnsKasteeltje/homey-energy-manual/pull/276).
No EV threshold, phase-transition, planner, Gate, hardware-write or
P1 policy changed in this auth repair.

## Incident evidence and likely defect

On 14 October 2026 a Homey EV phase writer reported
`EASEE_REFRESH_HTTP_401`; the Tesla could still charge 1×16 A and
complete its session. The then-current split legacy Logic variables
did not provide a single atomic token-pair update. A controlled
commissioning bootstrap restored a token pair and a read-only Easee
HTTP 200, but **that alone did not prove automatic refresh**.

The v0.4.7 atomic-bundle design was promoted via PR #264. Further
natural refresh failures on 17 October showed that atomic storage
alone had not corrected the refresh HTTP request. Before PR #276 the
refresh body contained only `refreshToken`, while the request also
sent `Authorization: Bearer <accessToken>` even if that access token
had expired. Three independently reviewed Easee client implementations
instead sent both tokens in JSON without that Bearer header. The
specific request-shape mismatch is a strong explanation for the
observed 401, but the full history of upstream token invalidation
or any concurrent refresh race has **not** been independently proven.

## Production design and corrected HTTP contract

- Keep exactly **one physical Easee EV writer** in the existing
  enabled Homey Advanced Flow and preserve its card IDs.
- The canonical private Homey Logic string
  `EM2_Easee_Token_Bundle_V1` stores
  `schema`, `accessToken`, `refreshToken`, `expiresAt`
  and a monotonic integer `revision` together in one JSON value.
  Old split token variables remain rollback-only, not live producers.
- Before refresh, re-read the bundle and reuse a valid newer revision
  if one has appeared; on a 401, never retry the rejected one-use
  refresh token. A successful refresh writes the complete new pair,
  expiry and revision together, then verifies the Logic readback.
- **PR #276, merged as
  `35a1f876234521143c67b65ed799a415bd57fc0f`:**
  `POST https://api.easee.com/api/accounts/refresh_token`
  with JSON body `{accessToken, refreshToken}`, headers
  `Accept: application/json` and
  `Content-Type: application/json`, **no Authorization Bearer
  header** for this operation. The distinct physical phase command
  still uses the access-token Bearer header.
- Missing/invalid bundles, expired/rejected auth, write/readback
  mismatch and unexpected responses remain bounded and fail closed.
  Access tokens, refresh tokens and passwords must never be printed,
  committed, put in notifications or pasted into chat.

### Concurrency and safety limits

Homey Logic offers no documented compare-and-swap. A single bundled
write plus readback reduces mixed-token failures but is **not a
transactional mutual-exclusion lock** for concurrent writer invocations.
The existing actuator RUNNING guard is not a distributed mutex.
There are no unlimited retries, background login loops or additional
token owners. After a successful remote refresh but failed Homey
Logic persistence, a new controlled bootstrap may be necessary
because the already-used refresh token cannot safely be replayed.

## Deployment and acceptance evidence — 17 October 2026

| Evidence | Observed result |
| --- | --- |
| GitHub code review | PR #276 merged to `main`, SHA `35a1f876234521143c67b65ed799a415bd57fc0f` |
| Pi source state | Clean `main` at the merged SHA; Pi drift check PASS |
| Focused regression | `node --test tests/control/ev/ev-phase-writer-v0.4.7-atomic-easee.test.mjs`: 10/10 PASS, including mock HTTP request/header contract |
| Predeploy safety | Actuator `STABLE`; backup, source guard, flow configuration guards PASS |
| Homey deployment | Single in-place update, exact readback PASS, four cards retained, enabled and not broken |
| Deployed script SHA-256 | `896c5be8ee97b22f91bfefbee6aae62cb59aee2d11e06af9563bee959ab2233e` |
| Natural charging | Charging resumed after 3P→1P transition; later 1P→3P and physical 3×7 A (about 5,001 W) |
| Token bundle before refresh | Revision `1792231554108`; post-bootstrap expiry 17 October 13:04:54 Europe/Amsterdam |
| Token bundle after natural cycle | Revision **`1792231554109` (+1)**, expiry **17 October 14:04:06 Europe/Amsterdam**, token still valid |
| Homey actuator after cycle | `STABLE`, reason `SAME_PHASE_CURRENT_APPLIED`, confirmed `3P` |

The +1 revision is the writer's refresh revision convention; a new
bootstrap uses a millisecond timestamp rather than an increment.
The new expiry, valid bundle and natural physical operation together
constitute **strong production evidence for a successful automatic
writer-owned token rotation**. There was no manually forced refresh,
Tesla start, phase change or additional hardware write. We did not
capture a network-level trace of the individual successful HTTP
request; avoid claiming independent packet-level verification.
One successful renewal does not eliminate the concurrent-refresh risk
or guarantee future renewals.

## Recovery / rollback

If an auth failure recurs, record only sanitized actuator reason,
revision, expiry and whether the token bundle was rotated; never dump
token values. Determine whether the problem is a stale/consumed token,
writer race, readback failure or changed Easee API request contract
**before** proposing another architecture.

The 0600 predeploy Homey Flow JSON backup is retained locally on the
Pi (17 October 2026). A prior v0.4.6 script and the old split Logic
values are *historical rollback material only*. Old split tokens may
already be revoked after rotation; never reactivate them assuming
validity. A controlled local interactive bootstrap can restore both
formats if rollback truly requires it, followed by an exact Homey Flow
readback. Do not trigger a physical EV actuator manually to test auth,
change the phase policy to mask an auth failure, or add a second
production Easee token writer.

Architecture ownership remains Pi planner → Homey realtime Gate /
single physical Easee writer, with P1 as actual net-import authority.

## Proposed 2026-10-18 KISS follow-up — not deployed (draft PR)

A new auth-only action card in the **existing EV Power v0.4.7 Homey Advanced
Flow** (same Flow ID, no new physical writer) is scheduled by a separate
15-minute cron trigger. Its source:
`apps/homey/control/ev/easee-auth-maintenance-v0.1.homeyscript.js`.
During controlled commissioning substitute the pinned
`__EM2_EASEE_BUNDLE_ID__` placeholder with the local private Homey bundle
variable ID; keep secrets exclusively in Homey Logic.

- At each 15-minute tick, read the canonical Homey token bundle; refresh only
  if remaining validity is under 20 minutes.
- No Easee charger physical calls, phase/current commands, Flow triggers,
  pauses/resumes or Pi token service from the maintenance action.
- The existing writer remains the sole **physical** Easee writer and retains
  its own lazy refresh/retry when a phase command requires it. Both entry
  paths share one token bundle. Homey Logic does **not** provide CAS or a
  cross-invocation lock; race risk is not claimed eliminated.
- HTTP refresh 401, invalid bundle and failed persistence remain bounded and
  fail closed; push via the existing Homey owner-push/Timeline fallback,
  deduplicated against an active prior alert.
- The actor status preserves an active `authAlert` across physically STABLE
  or OFF 0A executions. Only a successful Easee Cloud HTTP operation or
  successful maintenance refresh explicitly resolves the alert. This is
  authentication health, independent of physical charging status.
- No automatic password login or credential storage; a revoked single-use
  refresh token requires controlled local interactive bootstrap.

**Deployment gate (not done in this PR):** focused tests, architecture/security
checks, exact in-place Homey Flow backup and readback, cron trigger wired
exclusively to the auth-only action, only one new action card and one trigger;
verify no charger writes across maintenance; verify real token revision/expiry
after one natural refresh, and owner push on sanitized simulated or observed
auth failure (do not intentionally invalidate production credentials).
No main/Pi/Homey production deployment without separate acceptance.
