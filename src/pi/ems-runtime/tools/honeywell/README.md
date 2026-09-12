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
│   └── account.env
├── cache/
│   └── ... token/cache files ...
├── output/
│   └── ... generated JSON ...
└── probe/
    └── probe_honeywell.py
```

Credentials, tokens, caches and generated output must never be committed to GitHub.

## Library

Initial probe uses `evohome-async` 2.1.0 (`evohomeasync2` namespace), an asyncio client for the Resideo Total Connect Comfort EU/EMEA API. Python >=3.13 is required by that release.

The vendor API exposes zone status and schedules. The probe intentionally calls only read operations (`update()` and `get_schedule()`).

## First probe

The first probe is deliberately diagnostic. It reports per zone:

- zone name/id;
- current room temperature;
- current target temperature;
- current setpoint mode;
- current schedule switchpoint;
- next schedule switchpoint.

It does not write the canonical EMS SQLite database yet and does not install a timer/service. That happens only after the data contract and API behaviour have been validated against the live installation.

## Security

Create `config/account.env` locally from `config/account.env.example` and set permissions to `0600`. Do not pass credentials as CLI arguments because that can leak them into shell history/process inspection.

## Failure policy

Honeywell cloud data is advisory context for the future thermal planner. Cloud/API failures must be fail-soft: no heating control authority changes, no inferred write action, and no interruption of the existing EMS/P1/PV history chain.
