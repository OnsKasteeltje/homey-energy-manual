# PV Cloud SHADOW observation V0.1 — 24 October 2026

This optional Pi-owned integration observes the two GoodWe inverters over
the SEMS+ Web API and the SolarEdge SE3680H over the official Monitoring API.
It exists solely to assess whether alternate cloud evidence can repair the
household PV observation quality gap left by stalled Homey GoodWe Cloud data.

Code: services/pi/integrations/pv_cloud/collect_shadow.py.
Lifecycle: RUNNING / READ_ONLY SHADOW on the Pi since 24 October 2026;
15-minute timer explicitly enabled by the operator. This is not enabled by
the central EMS deploy script. The optional SolarEdge V1 source is deliberately
disabled after its deprecation HTTP 503; only GoodWe SEMS+ is configured.
Nine focused offline tests cover source exclusions and status semantics.
No changes to Homey devices, planner, P1, EV, WW or heating control.

Data: private latest JSON and 192-sample bounded rolling JSON history,
atomic owner-only writes. Fetch timestamps are not inverter measurement
timestamps. GoodWe physical sample time is unknown. SolarEdge site
lastUpdateTime does not prove power sample age. Missing power is null.
Only fully configured sources participate in overall status. Disabled sources
remain UNCONFIGURED diagnostically, do not receive API requests, and do not
cause DEGRADED. If all active sources report expected evidence statuses, overall
status is OBSERVED_UNVERIFIED_FRESHNESS; configured failures yield DEGRADED,
and no sources yields NO_ACTIVE_SOURCES. A healthy GoodWe-only configuration is
therefore not degraded by intentionally disabled SolarEdge. No cloud input can
influence P1 authority, home load, realtime flex or PV self-use accounting.

Credentials remain local in /etc/ems/pv-cloud-shadow.env, mode 0600;
no passwords, access keys or tokens in GitHub, stdout or diagnostic errors.
SEMS+ Web API is undocumented and may break or rate-limit. Enable the
15-minute timer was manually enabled after acceptance and source checks.
