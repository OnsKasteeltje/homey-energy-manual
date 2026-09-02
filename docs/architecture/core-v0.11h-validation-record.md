# Core v0.11h validation record

**Status: PREP ONLY / NOT DEPLOYED**

Validation date: 2026-09-02

## Immutable identities

- Runtime baseline commit: `bd4edecc219c035399a18671429c2cf24eaea1be`
- Runtime baseline path: `src/homey/core/core-v0.11g.live-homey.js`
- Runtime baseline Git blob: `0bdd1fd7228cddcd2c5331df1dbbcfcaa3aab715`
- Prepared branch: `prep/core-v0.11h-ww-thermostat-low-power`
- Validated branch head: `d088440e5626c9ba7ae6a9d153d1b090c6ab1721`
- GitHub Actions run: `33673543895`
- Deterministically materialized candidate Git blob: `c88647e08b85631cd27bb109b35a58a569445dea`

The candidate is generated from the immutable v0.11g source by `src/homey/core/tools/materialize-core-v0.11h.sh`. The materializer fails closed unless the baseline blob matches and exactly four semantic replacements plus two identity/version replacements are applied.

## Green validation gates

GitHub Actions job `validate-v011h` completed successfully. The following steps all passed:

1. Full-history checkout.
2. Materialization from immutable v0.11g baseline.
3. HomeyScript syntax check inside an async wrapper, matching HomeyScript's allowance for top-level `await`/`return` semantics rather than treating the script as CommonJS.
4. WW thermostat regression matrix: 10/10 PASS.
5. Candidate remains generated-only and is not silently committed as runtime source.
6. Surgical diff records only the intended Core v0.11h identity change and WW thermostat-verification change.

## Regression evidence

- 2026-09-02 incident: high-power boiler + 900 W import after run-lock -> `BOILER_OFF / WAIT_IMPORT`.
- Minimum PV run-lock remains -> `HOLD / RUN_LOCK`.
- Valid low-power thermostat evidence -> `HOLD / THERMOSTAT_VERIFY`.
- Re-heating during verification -> `BOILER_OFF / THERMOSTAT_VERIFY_ABORT`.
- Verification expiry at 20 minutes -> `BOILER_OFF / THERMOSTAT_VERIFY_EXPIRED_OFF`.
- Planner high-power stop remains -> `BOILER_OFF / PLANNER_SLOT_END`.
- Catch-up remains higher priority -> `HOLD / CATCHUP`.
- Mode-off remains hard-off -> `BOILER_OFF / BLOCKED_MODE`.
- After 19:00 remains hard-off -> `BOILER_OFF / AFTER_DEADLINE`.

## Remaining deployment gate

No Homey change is authorized by this record. Before deployment, record the exact current Homey Core flow configuration/readback and rollback procedure, then deploy the entire reviewed v0.11h candidate as one unit only after explicit approval. The first post-deploy validation must be observational and must not induce artificial loads.