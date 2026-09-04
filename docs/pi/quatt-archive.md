# Pi Quatt history archive

## Goal

Preserve Quatt telemetry outside Homey so that historical analysis and future
load forecasting do not depend on Homey Insights retention or aggregation.

The Quatt data is **forecast/analysis input only**. This archive does not control
Quatt and must not write device capabilities or Flow state.

## Scope

The first archive candidate set is intentionally small:

- electrical/energy power reported by the Quatt CIC;
- outside temperature (including per-heat-pump variants);
- thermal power (including per-heat-pump variants);
- COP (including per-heat-pump variants);
- incoming and outgoing water temperatures;
- thermostat heating request / central-heating request.

Additional capabilities can be added after data quality has been assessed.

## Data model

`quatt_archive_normalize.py` stores samples in SQLite using:

- Homey Insights log ID;
- UTC timestamp;
- numeric value when present;
- explicit `is_gap=1` for Homey `null` values;
- source resolution used by the Homey request.

Nulls are preserved rather than discarded because they may represent an idle
period or unavailable telemetry and are useful for later data-quality analysis.

## Security boundary

No Homey credential belongs in GitHub.

When the HTTP fetch layer is added, credentials must only exist locally on the
Pi in a file readable by the service account, or in a systemd environment file
with restrictive permissions. The fetcher must be read-only and limited to
Homey Insights retrieval.

## Current status

Phase 1 provides a null-safe local importer and schema. The transport/fetch
layer is deliberately not hard-coded yet: authentication and the exact Homey
API route must be verified against the Homey Pro/API environment before any
credential is provisioned on the Pi.

This separation allows the data handling to be tested without Homey writes or
secrets.
