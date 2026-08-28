# Homey EMS Core runtime source

This directory is the versioned source baseline for the Homey Advanced Flow **EM v2 | 00 Core Tick**.

- Homey Advanced Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`
- Current captured runtime: `core-v0.10.14.js`
- Homey runtime status at capture: `enabled=false`, `broken=false`
- Capture commit: `2842a3e03571989e22610cc3af1767b5d4fed4c5`
- Safety: Core is SHADOW/read-only and must not perform physical device writes.

## Change rule

Never reconstruct or simplify the Core script while deploying a change. Start from the latest versioned baseline, make the smallest reviewable diff, validate that all existing functional sections are retained, and only then deploy the complete script to the existing Advanced Flow.

For fan-out optimisation, timestamps/heartbeat metadata must not create downstream Logic change events when the semantic state or control intent is unchanged. Public-state publication freshness is transport metadata and must not be used as an internal control trigger.
