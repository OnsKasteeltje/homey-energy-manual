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

## GoodWe partial-power / counter-only observations (24 October 2026)

SEMS+ can omit both inverter `pac` fields after sunset while continuing to
return valid `eday` and `etotal` counters. With both distinct inverters and
both counters present, the Pi collector records
`COUNTER_ONLY_SOURCE_TIME_UNKNOWN` instead of `INCOMPLETE` and the aggregate
status becomes `OBSERVED_COUNTER_ONLY_UNVERIFIED_FRESHNESS` (not full power
health). Individual `powerW` and `sumInverterPowerW` remain null, **never 0 W**.
If identities or required counters are absent, the observation remains
`INCOMPLETE`/`DEGRADED`. The read-only Evaluatie API accepts the counter-only
samples as counter evidence, advances its latest Pi-fetch timestamp and displays
unknown power explicitly. It never interpolates quarter-hour PV production,
changes source authoritativeness or touches Homey/P1/SolarEdge control.



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

## Durable GoodWe day-counter history (V0.1)

The existing SEMS+ 15-minute collector archives two validated inverter
day/lifetime counters to the one existing EMS SQLite history:

    /home/jeroen/ems/data/ems-history.sqlite (existing EMS history DB, dedicated goodwe_counter_observations table)

Observations are keyed by Pi fetch timestamp and hashed inverter identity.
On first run the current 192-sample SHADOW ring is imported once. Subsequent
valid samples append idempotently, including counter-only night observations.
No extra cloud calls or timer, no legacy history rewriting, no fabricated zeros.
The collector's systemd unit needs a scoped data-directory write exception;
no chmod of the existing EMS SQLite file is permitted.

The existing single read-only API GET /web/analysis/pv-cloud/day/YYYY-MM-DD now includes SEMS+
reported day-counter totals and, separately, the lifetime-counter change
within the available observation window. Identity changes and counter
decreases fail closed (no numeric day value). A late-day reported counter
is not independently proven to be the final inverter-measured day value.

The Evaluatie page shows this durable SEMS+ day source in its existing GoodWe panel
through the same single read-only API call. The bounded JSON history remains
only diagnostic SHADOW state, not a second durable history store.
SEMS+ day/lifetime counters must NOT be redistributed into quarter-hour
energy. Only fully covered timestamped pSystem power curves are used
by the separate canonical history source selector. P1/SolarEdge
and all physical control consumers stay unchanged.
## Canonical house-history GoodWe source selection (25 October 2026)

The existing history builder `services/pi/history/build_house_energy_history.py`
now uses fully covered (900-second) SEMS+ station `pSystem` quarters
from 2026-10-25 00:00 Europe/Amsterdam. The two Homey GoodWe counter
feeds remain historical/rollback evidence only before this date,
never a fallback after it. Within each complete cloud quarter the
15-minute station kWh is divided across the existing, shorter P1
intervals proportionally to time and marked `estimated`. The sum of
these intervals preserves the original quarter kWh if P1 coverage
is complete. Partial/missing cloud quarters are unknown, not zero;
house and total PV kWh remain NULL while P1 import/export persists.
The builder adds only one nullable combined GoodWe history column,
`pv_goodwe_sems_kwh`; the two older per-inverter GoodWe columns
remain NULL after cutover. No fake model-to-serial mapping.

The cloud API's `eligibleForHouseBalance=false` applies to the
raw SHADOW web payload, **not** to the independently validated,
fully covered archived curve table selected by the canonical
history builder. Control remains P1-led and does not use SEMS+.
No additional SEMS+ polling, separate database or systemd service.

## Historical SEMS+ minute power curve (SHADOW, 25 October 2026)

The **same** existing 15-minute collector queries the SEMS+ historical
`pSystem` station curve once per run. This is a separate source from the
live `eday`/`etotal` counters. `pSystem` comes back in kW at local minute
timestamps (`tp`), and the code integrates observed segments into UTC
quarter-hour energy. Only completed quarters with at least 12 minutes of
observed-segment coverage are retained, in the existing
`ems-history.sqlite.goodwe_sems_curve_15m` table. Missing minutes or DST
ambiguous local timestamps are never treated as zero. No local GoodWe
connection, new database, timer, web endpoint, Python dependency or
physical write is required.

Existing read-only Evaluatie GoodWe API returns a
`historicalQuarterEvidence` object showing quality-gated quarters and
the sum over **covered** quarters only. The SHADOW endpoint itself never writes `house_energy_intervals`.
The separate history builder selects complete persisted quarters from
the declared cutover; P1 control never uses this cloud source.
An optional one-time `--curve-day YYYY-MM-DD` permits an explicit
historic backfill with this same collector, with existing credentials.

The rate is one extra historical HTTP request + authentication per normal
15-minute collector run. If SEMS+ rejects the request, the existing live
counter path remains operational, and only historical evidence is missing.

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
