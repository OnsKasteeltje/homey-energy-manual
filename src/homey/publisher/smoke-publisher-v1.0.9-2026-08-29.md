# Publisher v1.0.9 HARD-GATE smoke — 2026-08-29

## Runtime

- Flow: `EM v2 | 40 Data | Publisher v1.0.9 HARD-GATE LOW-LOAD`
- Flow ID: `fe84bc17-72d4-4fbb-9a69-b3d751b0ffcd`
- Enabled: `true`
- Broken: `false`
- Trigger: `EM2_Public_State changed` + 2 s settle
- Manual start retained for recovery/smoke.

## Load change

The publisher is still event-driven, but actual external publication is now hard-gated to at most once per 15 minutes.

Within the 15-minute gate window the flow performs only five targeted Logic reads and then returns immediately. It performs no GitHub GET/PUT and no publisher diagnostic/status writes in that path.

An allowed publication performs the existing GitHub rolling-state update and the existing compact status writes. `meta.min_publish_interval_sec` is now `900` and, unlike v1.0.8, is enforced in runtime logic.

## Smoke

Exactly one controlled manual start was executed immediately after deployment.

Result from Homey: `Successfully started the Flow.`

No `Too many requests` response occurred during the deployment or smoke.

No device or actuator access exists in this flow.

## Result

**PASS** — v1.0.9 is deployed and runnable without immediate Homey throttling. Sustained A/B evidence is still required before attributing the structural throttling exclusively to the previous publisher behavior.
