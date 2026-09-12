# Honeywell / Evohome tool

Read-only Raspberry Pi adapter for Honeywell/Resideo Evohome data used by the EMS thermal observer and future PV-preheat shadow planner.

## Ownership boundary

- Honeywell remains comfort authority.
- The existing Honeywell -> OpenTherm -> Quatt/CV control path is not modified.
- This tool does not write zone temperatures, schedules, thermostat modes, OpenTherm values or devices.
- Homey remains the preferred future execution layer for any explicitly approved temporary override/reset action.
- The Pi consumes Honeywell state/schedule data only as planning context.

## Runtime layout

Deploy repository code to:

```text
/home/jeroen/ems/runtime/tools/honeywell/
```

Expected local-only runtime material:

```text
/home/jeroen/ems/runtime/tools/honeywell/
├── .venv/
├── config/
│   ├── account.env
│   └── zone-map.json
├── cache/
│   └── oauth-token.json
├── output/
│   ├── honeywell-state.json
│   └── honeywell-schedule.json
├── honeywell_common.py
├── collect_honeywell.py
├── collect_honeywell_schedule.py
└── probe/
    └── probe_honeywell.py
```

Credentials, tokens, caches and generated output must never be committed to GitHub.

## Library and authentication

The tool uses `evohome-async` 2.1.0 (`evohomeasync2` namespace), an asyncio client for the Resideo Total Connect Comfort EU/EMEA API. Python >=3.13 is required by that release.

The library exposes access-token, expiry and refresh-token state. The EMS persists those values in `cache/oauth-token.json` with mode `0600`, allowing separate collector processes to reuse a valid access token or refresh token instead of performing a username/password grant on every run.

`config/account.env` is still required as the final fallback when no usable token/refresh token is available. It is parsed using Bash semantics because the local credential file may contain values produced with `printf %q`.

## Poll classes

The cloud workload is deliberately split:

- `collect_honeywell.py` is the state collector. Intended cadence: every 5 minutes. It calls `update()` and records current zone temperature, target and setpoint mode. It does **not** fetch schedules.
- `collect_honeywell_schedule.py` is the schedule collector. Intended cadence: every 6 hours, with an optional explicit refresh after a detected schedule/configuration change. It calls `get_schedule()` per mapped zone and records current/next switchpoints.

No systemd timer is enabled until the collectors and token reuse have been validated manually on the Pi.

## Outputs

`output/honeywell-state.json` uses `EMS_HONEYWELL_STATE_V0.2` and contains the normalized 8-zone current state under canonical EMS/Homey names.

`output/honeywell-schedule.json` uses `EMS_HONEYWELL_SCHEDULE_V0.1` and contains current/next Honeywell switchpoints under the same canonical zone mapping.

Both outputs are written atomically only after a successful cloud read. A failed vendor call therefore leaves the previous valid output intact; downstream consumers must use `generatedAt` freshness and fail closed when data is stale.

## First probe

The diagnostic probe remains available for manual inspection. It reports per zone:

- zone name/id;
- current room temperature;
- current target temperature;
- current setpoint mode;
- current schedule switchpoint;
- next schedule switchpoint.

It does not write the canonical EMS SQLite database.

## Security

Create `config/account.env` locally from `config/account.env.example` and set permissions to `0600`. Do not pass credentials as CLI arguments because that can leak them into shell history/process inspection.

The token cache contains live OAuth credentials and is therefore also mode `0600`; the cache directory is mode `0700`.

## Failure policy

Honeywell cloud data is advisory context for the future thermal planner. Cloud/API failures must be fail-soft: no heating control authority changes, no inferred write action, and no interruption of the existing EMS/P1/PV history chain.
