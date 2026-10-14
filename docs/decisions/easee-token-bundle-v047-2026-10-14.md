# Easee rotating-token recovery — v0.4.7 candidate (2026-10-14)

**Status: PROPOSED ONLY — NOT DEPLOYED.** The production Homey physical Easee
writer remains v0.4.6, Advanced Flow `fea23193-a03f-49dd-9780-7e72ee48747d`.
No EV threshold, phase-transition, planner, gate, hardware-write, or P1 policy
changes are part of this proposal.

## Incident evidence

On 2026-10-14 the Homey EV writer reported `EASEE_REFRESH_HTTP_401`.
Three separate Homey Logic variables for access, rotating refresh and expiry
were populated; the expiry was 2026-10-14T09:37:06Z. The Tesla continued charging
at 1 × 16 A and later finished normally. The commissioning bootstrap produced a
fresh Easee login token pair and a **read-only Easee HTTP 200** followed.

**Proven:** refresh HTTP 401 prevented a successful phase-cloud refresh at the
failed invocation. **Not proven:** whether the root cause was lost/rotated tokens,
concurrent invocations, partial Homey Logic update, revoked session or upstream
Easee API behavior. A 200 after bootstrap does not prove future automatic
rotation works.

## Candidate design

- Retain **one physical EV writer** in Homey; use existing flow and card IDs.
- Bootstrap additionally provisions one private Homey Logic string variable:
  `EM2_Easee_Token_Bundle_V1`, containing the schema, access/refresh token,
  expiry and monotonic revision in **one JSON value**.
- The candidate v0.4.7 writer reads/updates **only that canonical bundle** for
  Easee phase-mode cloud operations. Normal Easee Homey-app native action cards
  remain unchanged.
- Before refresh the writer re-reads the bundle; if a newer revision has already
  been stored, it uses it instead of consuming an older one-use refresh token.
  After a refresh HTTP 401 it checks once whether another execution already
  published a valid newer bundle; it never retries the rejected refresh token.
- On successful refresh it writes the *entire* token pair + expiry in one Logic
  update and reads back to check that the revision and token pair match.
- Missing/invalid/uncommissioned bundle, failed refresh, write/readback conflict
  and unacceptable error responses remain **fail closed**.
- Access/refresh tokens and password must never be committed, logged, pasted
  into terminal output or sent to GitHub. The bundle Logic ID is not a secret.

### Concurrency limitation

Homey Logic does not expose a documented atomic compare-and-swap transaction.
The above minimizes stale-token races, but **does not guarantee mutually
exclusive refresh across truly concurrent writer invocations**. The existing
bounded actuator RUNNING gate remains in effect, but is not a distributed mutex.
Do not describe this patch as a proven global single-flight token service.
If a 401 recurs after v0.4.7, investigate a single durable Pi-side token-owner
service rather than adding unbounded Homey polling/retries.

A successful Easee refresh followed by a failed Homey Logic write also cannot
be safely rolled back at Easee; this requires fresh login/bootstrap. No
password-based automatic retries.

## Safe commissioning after PR merge / reviewed tests

Prerequisites: Tesla charging completed, EV planner/gates stable, no concurrent
Homey maintenance in another session. Follow the mandatory low-load Homey
access guideline. Do **not** start the physical EV writer manually for tests.

1. On Pi, sync clean `main` after the PR is merged and verify the approved
   v0.4.7 source/commissioning scripts exist. No runtime change yet.
2. Run the existing locally interactive command, not in chat:

   ```bash
   cd /home/jeroen/ems/repo/homey-energy-manual
   python3 services/pi/commissioning/bootstrap_easee_homey_tokens.py
   ```

   This creates/updates the three legacy rollback values **then** the new
   atomic bundle. Confirm only `PASS` and four `PRESENT` reports. Never print
   the tokens. The new bundle Logic ID is stored in the existing 0600 Pi registry.
3. Run targeted candidate preparation (one live flow read; no writes):

   ```bash
   python3 tools/maintenance/homey/prepare_easee_v047_candidate.py
   ```

   It verifies the *exact* deployed v0.4.6 script against canonical v0.4.6,
   replaces the sole pinned bundle-ID placeholder and writes a local 0600
   candidate JSON. Any unexpected live drift **must stop** the deployment.
4. Test and use the controlled deployer **dry-run first**:

   ```bash
   node --test tests/control/ev/ev-phase-writer-v0.4.7-atomic-easee.test.mjs
   node --test tests/control/ev/ev-phase-writer-v0.4.6-off-zero.test.mjs
   python3 -m py_compile services/pi/commissioning/bootstrap_easee_homey_tokens.py tools/maintenance/homey/prepare_easee_v047_candidate.py
   python3 tools/maintenance/homey/homey_flow_deploy.py \
     --id fea23193-a03f-49dd-9780-7e72ee48747d \
     --candidate /home/jeroen/ems/data/deploy/easee-v047-candidate.json
   ```

   Expected: `DIFF`, dry-run write **BLOCKED**, predeploy backup present.
   The deployer may return exit 1 for an intentional dry-run difference.
5. After explicit APPLY approval and reviewed gate results, use the **same**
   deployer and candidate path with `--apply`. Require exact post-write
   readback hash and v0.4.7 flow name/version. Do not change charger settings,
   force a phase transition or force an artificial refresh.
6. Observe the next **natural** token expiry and normal EV opportunity.
   Verify no auth alert, API 401, stale bundle or unexpected Homey 429.
   HTTP 200 immediately after a bootstrap alone is not rotation proof.

### Rollback

The normal controlled deployer preserves the predeploy flow JSON.
If rollback is needed *after the bundle has rotated*, the three legacy token
variables may no longer be valid. **Bootstrap again locally** to restore both
formats, then restore the backed-up v0.4.6 writable flow with the controlled
deployer and verify the readback. Never assume a previous refresh token can be
reused. Do not change EV charging policy to mask authentication failure.

## Required acceptance

- Contract and bootstrap syntax tests PASS in CI.
- Exact live v0.4.6 source verified, candidate prepared without a Homey write.
- Explicit apply approval, predeploy backup and postdeploy exact readback PASS.
- Real natural refresh and subsequent normal 1P/3P operation separately proven.
- Only then update current-state and canonical live architecture documentation
  to reflect the promoted version, not before.
