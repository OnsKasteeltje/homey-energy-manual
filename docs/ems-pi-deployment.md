# EMS Pi Deployment

## Purpose

The Raspberry Pi EMS runtime is deployed from the Git repository.

Git is the source of truth for:

- EMS runtime source
- EMS systemd units
- deployment and drift-check tooling

Runtime state and generated data remain outside Git.

## Repository layout

```text
src/pi/ems-runtime/
    EMS Python runtime source

deploy/systemd/
    systemd service and timer definitions

scripts/deploy_ems_pi.sh
    controlled deployment

scripts/ems_pi_drift_check.sh
    runtime drift detection
