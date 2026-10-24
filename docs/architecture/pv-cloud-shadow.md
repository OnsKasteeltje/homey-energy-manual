# PV Cloud SHADOW observation V0.1 — 24 October 2026

This optional Pi-owned integration observes the two GoodWe inverters over
the SEMS+ Web API and the SolarEdge SE3680H over the official Monitoring API.
It exists solely to assess whether alternate cloud evidence can repair the
household PV observation quality gap left by stalled Homey GoodWe Cloud data.

Code: services/pi/integrations/pv_cloud/collect_shadow.py.
Lifecycle: DRAFT / NOT DEPLOYED / SHADOW. One-shot implementation, six
offline tests, opt-in service/timer templates, no changes to existing deploy
scripts, Homey application devices, planner, P1, EV, WW or heating control.

Data: private latest JSON and 192-sample bounded rolling JSON history,
atomic owner-only writes. Fetch timestamps are not inverter measurement
timestamps. GoodWe physical sample time is unknown. SolarEdge site
lastUpdateTime does not prove power sample age. Missing power is null.
Both source results must be evaluated independently. No cloud input can
influence P1 authority, home load, realtime flex or PV self-use accounting.

Credentials remain local in /etc/ems/pv-cloud-shadow.env, mode 0600;
no passwords, access keys or tokens in GitHub, stdout or diagnostic errors.
SEMS+ Web API is undocumented and may break or rate-limit. Enable the
15-minute timer only after a manual read-only acceptance and source checks.
