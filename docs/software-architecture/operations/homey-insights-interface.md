---
component: operations
title: Pi Homey Insights Interface
version: 1.0.0
status: active
architecture_status: implemented
last_verified: 2026-09-09
---

# Pi Homey Insights Interface

## Purpose

The EMS Raspberry Pi already contains an interface for collecting historical Homey Insights data. Reuse this interface for historical analysis instead of installing a separate Homey CLI or rediscovering Homey authentication.

Typical uses include reconstructing historical WW/boiler energy use, weekday profiles, EV/device history and other Homey Insights based analyses.

## Existing implementation

The Pi runtime contains the Homey Insights collector:

- `runtime/datastore/collect_homey_insights.py`
- systemd service: `ems-homey-insights.service`
- systemd timer: `ems-homey-insights.timer`

Backups of these components may also exist below `/home/jeroen/ems/backup/`; these are not the canonical live implementation.

## Authentication

The existing Pi tooling uses the Homey API key file:

`~/.config/ems-pi/homey-api-key`

Never print or commit the token value. Diagnostics should only verify that the file exists and is non-empty.

Repository tooling also uses the `homey-api` Node package where appropriate. Example: `tools/deploy-planner-v051-event-refresh.mjs` reads the same API-key file.

## Operational rule

Before creating a new Homey API/Insights client or installing Homey CLI:

1. Inspect and reuse `runtime/datastore/collect_homey_insights.py`.
2. Check `ems-homey-insights.service` and `ems-homey-insights.timer` status.
3. Verify the API-key file exists without exposing its contents.
4. Prefer bounded historical Insights requests over repeated broad Homey reads.
5. Respect the Homey API load/throttling rules in `homey-api-load-map.md` and `05-homey-api-load-governance.md`.

## WW historical analysis

For WW/boiler analysis, Homey Insights can be used to extend the Pi's locally archived `history/days/YYYY-MM-DD.json` series further back in time. The local day archive exposes `boilerW` and `boilerOn`, but its retention/history may be shorter than the history available in Homey Insights.

The intended analysis path is therefore:

`Homey Insights -> Pi collector -> bounded historical export -> daily boiler kWh -> weekday/statistical profile`

This makes Homey Insights the preferred fallback/source for historical periods that predate the Pi day archive.

## Discovery / diagnostics

Safe first checks on the Pi:

```bash
systemctl status ems-homey-insights.service --no-pager -l
systemctl status ems-homey-insights.timer --no-pager -l

if [ -s "$HOME/.config/ems-pi/homey-api-key" ]; then
    echo "PASS: Homey API key exists (content hidden)"
else
    echo "FAIL: Homey API key missing/empty"
fi

sed -n '1,260p' /home/jeroen/ems/runtime/datastore/collect_homey_insights.py
```

Do not assume a globally installed `homey` CLI. On 2026-09-09 the Pi returned `homey: command not found`, and no local `./node_modules/.bin/homey` was present in the repository. The existing collector/API-key path is therefore the canonical route for this EMS.

## Related documentation

- `docs/software-architecture/operations/homey-api-load-map.md`
- `docs/software-architecture/architecture/05-homey-api-load-governance.md`

## Verification history

2026-09-09: Pi filesystem discovery confirmed the existing `collect_homey_insights.py`, `ems-homey-insights.service`, `ems-homey-insights.timer`, and use of `~/.config/ems-pi/homey-api-key` by repository Homey API tooling.
