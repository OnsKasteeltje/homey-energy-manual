# Pi PV Cloud SHADOW collector V0.1

Read-only observations from the GoodWe SEMS+ Web API (two inverters) and
SolarEdge Monitoring API (one inverter). One Pi-owned script and optionally
one systemd oneshot/timer. This integration **does not** replace Homey, P1,
planner authority or historical energy accounting. No device commands, API
publication, Homey writes, EV changes or battery interactions.

## Evidence semantics

- GoodWe output: independent device keys (hash of serial), masked last four
  serial digits, individual AC watts and day/lifetime kWh. Do not infer schuur
  or CV mapping from output order. Previously observed tails: 0071 and 0285.
- GoodWe station power is an independent reading and may differ from the
  sum of per-inverter power due to source sampling skew.
- SolarEdge: AC watts, day/lifetime energy (API Wh converted to kWh),
  source-provided last *site* update string, not a power sample timestamp.
- fetchedAt means **received by Pi**, not **measured by inverter**. Both
  sourcePowerMeasuredAt fields remain null in V0.1: true physical sample
  times are not established. Missing/invalid values remain null, not 0 W.
- Overall status evaluates **only fully configured sources**. An omitted
  SolarEdge key/site disables SolarEdge polling (source status UNCONFIGURED),
  excludes it from activeSources and does not degrade healthy GoodWe observations.
  With GoodWe alone healthy, status stays OBSERVED_UNVERIFIED_FRESHNESS.
  A failed configured source results in DEGRADED; no configured sources yield
  NO_ACTIVE_SOURCES (never a false healthy result).
- eligibleForControl=false and eligibleForHouseBalance=false always.
  Do not join these cloud snapshots with P1 for realtime decisions.
- SEMS+ is an undocumented web API; source errors and rate limits use
  sanitized codes without raw request URLs or credentials.

Private local files (mode 0600):
- /home/jeroen/ems/runtime/state/pv-cloud-shadow-v0.1.json (latest).
- /home/jeroen/ems/runtime/state/pv-cloud-shadow-history-v0.1.json
  (last 192 observations, about 48 hours at the initial 15m schedule).

## Independent read-only EMS evidence view

The existing 192-sample rolling GoodWe SEMS+ history is projected by the
Web Data API on GET /web/analysis/pv-cloud/day/YYYY-MM-DD into a separate
Evaluatie panel. Each hashed inverter identity/serial suffix carries latest
received power, Pi-fetch-time observation bounds and monotonic same-source
lifetime counter delta. Missing data is unknown rather than zero. Source sample
timestamps are unknown and cumulative values have 0.1 kWh resolution.
The output is NOT per-quarter PV energy, and it is never added to the
canonical Homey/P1 PV balance or used for EV, WW, heating, or control.

The collector itself and its 15-minute timer stay unchanged, as do its
eligibleForControl=false and eligibleForHouseBalance=false boundaries.
Confirm suffix-to-physical-inverter mapping and source time quality before
a separate promotion of any historical accounting data.

## Optional setup (after draft PR review and merge only)

**No git pull or standard EMS deploy starts this service.** Nothing in the
existing EMS runtime is edited. Use an existing or newly created local
credential file, root:root 0600, exclusively on the Pi.

Run these steps in a local Pi terminal (do not paste secrets into chats):

    python3 -m venv /home/jeroen/ems/tools/pv-cloud-shadow/.venv
    /home/jeroen/ems/tools/pv-cloud-shadow/.venv/bin/python -m pip install -r services/pi/integrations/pv_cloud/requirements.txt
    sudo install -d -o jeroen -g jeroen -m 0750 /home/jeroen/ems/runtime/state
    sudo install -d -o root -g root -m 0700 /etc/ems
    sudo install -o root -g root -m 0600 /dev/null /etc/ems/pv-cloud-shadow.env
    sudoedit /etc/ems/pv-cloud-shadow.env

The env file must contain the following assignments, with real values entered
**locally**, not in the repo or terminal history:

    SEMSPLUS_STATION_ID="<the previously verified SEMS+ station UUID>"
    SEMSPLUS_ACCOUNT="<SEMS+ account>"
    SEMSPLUS_PASSWORD="<SEMS+ password>"
    SOLAREDGE_SITE_ID="<the previously verified SolarEdge site ID>"
    SOLAREDGE_API_KEY="<SolarEdge API key>"

SolarEdge key previously posted in chat should be rotated, checking any other
dependent integrations before doing so. The systemd EnvironmentFile is read
by root and the process executes under user jeroen, matching the existing
local-integrations pattern.

Explicit one-shot acceptance (unit is not started or enabled implicitly):

    ROOT=/home/jeroen/ems/repo/homey-energy-manual
    sudo install -m 0644 "$ROOT/services/pi/integrations/pv_cloud/ems-pv-cloud-shadow.service" /etc/systemd/system/
    sudo install -m 0644 "$ROOT/services/pi/integrations/pv_cloud/ems-pv-cloud-shadow.timer" /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl start ems-pv-cloud-shadow.service
    systemctl show ems-pv-cloud-shadow.service -p Result -p ExecMainStatus

Read source statuses and timestamps in the private latest JSON; a
successful oneshot does not imply both API reads succeeded. Once manually
validated, opt in to the 15-minute periodic collector with:

    sudo systemctl enable --now ems-pv-cloud-shadow.timer

To pause: sudo systemctl disable --now ems-pv-cloud-shadow.timer.
The timer is non-persistent: no catch-up burst after Pi downtime.
15m means approximately 96 SolarEdge overview requests per day; do not
increase frequency before checking real API freshness and rate limits.

Offline tests (no provider calls, no secret access):

    python3 -m unittest discover -s tests/integrations/pv_cloud -v

Nine focused checks: per-device counter/units, no fabricated zeros,
source-time honesty, sanitized failure isolation, source opt-out (GoodWe only
and SolarEdge only), no-active-source protection, private atomic state and
bounded history. No new CI workflow.
