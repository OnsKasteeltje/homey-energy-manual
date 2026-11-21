# Uptime Kuma — monitoring authority and guardrails

**Status:** source-only, opt-in candidate. Not deployed by the standard EMS
Pi installer. Existing Kuma 2.5.12 was confirmed Docker-healthy on
21 November 2026; its five previous monitors are retained. Notification
delivery is out of scope.

## Source-of-truth chain

\`\`\`text
Canonical Pi systemd and runtime data
  -> /usr/local/bin/ems-health (existing read-only evidence)
  -> optional 5-minute forecast health push publisher
  -> local Uptime Kuma: 127.0.0.1:3001 /api/push/<secret>
  -> operator availability dashboard
\`\`\`

The Raspberry Pi remains planning/state/health authority. Homey remains the
sole permitted physical executor. Kuma is **only a monitoring consumer**.
It must not control Homey, Easee, Honeywell, Quatt, AlphaESS, battery logic,
or any planner. The existing 15-minute forecast timer remains sole owner of
planner generation. No polling of appliances, cloud APIs or Homey is added.

The forecast monitor checks the existing bounded \`ems-health\` fields:
\`emsFunctions.forecastChain\`, \`emsData.dynamicPlan\`, \`emsData.wwPlan\`.
All must be \`OK\`. A recovered past failure must not keep this individual
monitor DOWN, and a different degraded function must not be misreported as
forecast failure. Missing/invalid current evidence yields a bounded DOWN
reason. Lack of pushes after a publisher/Pi outage is a different failure
than explicit DOWN based on health evidence.

## Deployment and information security

- The versioned script and systemd units are **opt-in**, not auto-installed,
  auto-enabled or invoked by the standard EMS deployment.
- The token-bearing Push URL is private, stored in
  \`/etc/ems/kuma-forecast.env\` with 0600 root ownership, and never
  committed to this public repository or to \`docs/data\`.
- This publisher accepts only HTTP to local loopback port 3001 and never
  prints the secret URL, telemetry, or exceptions containing it.
- No new Caddy/Tailscale/public API route, firewall opening, alert endpoint,
  Homey publication, second planner timer, or control authority is created.
- The existing Kuma port 3001 listens on host interfaces; review exposure
  separately rather than silently changing the established ingress.
- Source, tests, architecture and runbook are committed together before
  any controlled runtime installation. A Git commit is not a Pi deployment.

## Diagnostic rule

Inspect canonical \`ems-health\` forecast and plan statuses first, then
the read-only push service journal, and only then Kuma monitor/heartbeat.
Do not use Kuma's network availability checks to infer healthy planning.
The 21 Nov 2026 Homey WW-fetch timeout at 20:18 and subsequent successful
20:33 forecast run illustrate the difference between a transient incident,
current planner health, and independent website reachability.

Operations/validation/rollback: \`docs/operations/uptime-kuma.md\`.
