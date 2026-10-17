# Daily Heating Evaluation V0.1 — observational evidence

**Mode: READ_ONLY / SHADOW.** No heating control, Honeywell writes, Homey flow,
Quatt command, extra collector, or GitHub telemetry publisher.

Canonical data: `ems-history.sqlite` (`measurements_15m`,
`house_energy_intervals`, observed raw `measurements`). The daily evaluation
reads the database using SQLite read-only/query-only, and uses eight Honeywell
thermostat zones as **observations**. The existing six Heating control rooms
are unchanged. This is neither the Honeywell comfort authority nor a second
planner or the scheduled-step-up `Thermal Learning Episodes V0.1` model.

`services/pi/history/daily_heating_evaluation.py` generates a completed
Europe/Amsterdam calendar day's whole-day and four time-block reports:
`00–09`, `09–12`, `12–17`, `17–24`. Day boundaries remain local (including
DST); all joins/integrals operate on UTC timestamps. It records:

- complete 15-minute Quatt electrical energy and HP1/HP2 heat **sensor** energy;
  HP1 heat/electricity ratio only on paired complete quarters (not SCOP);
- mean Quatt `heating_on` and outside temperature on complete quarters;
- eight rooms' paired 15m mean temperature/setpoint evidence, below-setpoint
  indicators and completeness, but **not** proven individual zone heat demand;
- archival P1-import/export and three-inverter PV accounting on exactly
  overlapping intervals. Source `held` and `estimated` PV are included **with
  explicit hour coverage**; `gap` and `discontinuity` are excluded, without
  replacing missing energy with zero. Derived house/PV self-use requires >=95%
  paired coverage and a physically nonnegative PV-export balance;
- original CiC supervisory mode observations, mode 3/4 selection count and
  observed whole-house gas-counter span, never flame proof or room gas;
- `GOOD`, `PARTIAL` or `INSUFFICIENT` with quality issues and limitations.

The report does not infer heating savings, specific PV electricity delivered
to Quatt, room heat loss or a validated preheat horizon. 15m Honeywell means
can conceal a short setpoint change or ordinary thermostat hysteresis.

## Production scheduling and data ownership

No new timer. The existing `ems-history-daily.timer` runs at **00:20 local**.
After the existing `build_daily_energy_history.py` and
`daily_performance_evaluation.py`, systemd starts the new report in best-effort
mode (`ExecStart=-...`). A failure logs a diagnostic and **does not make the
established daily history/EV performance pipeline fail**. This also means a
successful systemd result alone does not prove heating evaluation succeeded;
check journal, dated JSON and `quality.status` separately.

Pi-private outputs:

- `/home/jeroen/ems/data/heating-daily-evaluation.json` (latest successful day)
- `/home/jeroen/ems/data/heating-daily-archive.json` (one keyed record per day)

Only completed local calendar days are accepted. Files are atomically replaced,
created mode 0600; existing incompatible archives fail closed and are not
silently reset. An unsuccessful report must not change the previous archive.
For diagnosis/backfill (read-only on DB):

```bash
python3 /home/jeroen/ems/runtime/history/daily_heating_evaluation.py 2026-10-17 --no-write-output
python3 /home/jeroen/ems/runtime/history/daily_heating_evaluation.py 2026-10-17 --archive-only
```

A controlled Pi deploy must sync the new managed source and matching systemd
unit, then `systemctl daemon-reload`; do not independently enable a timer or
restart unrelated EMS services. Commissioning proof should check one manual
read-only/no-output invocation, one completed scheduled daily run, JSON schema,
quality and archive idempotence. Do not treat GitHub merge as deployed.

The website Analysis view is **deferred**, to consume validated local reports
through the existing private Pi API. Do not put the private archive in GitHub
Pages or `docs/data`. Thermal Learning remains `UNASSESSED` until sufficient
comparable data supports a careful empirical model.
