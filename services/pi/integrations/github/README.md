# GitHub integration

This directory contains the remaining Pi-side GitHub integration used for the authenticated Tesla deadline command transfer.

## Active scope

- `ev/fetch_deadline_command.py` retrieves the accepted Tesla deadline command from the existing GitHub command-transfer boundary.
- GitHub is **not** a runtime transport dependency for Homey → Pi state or Pi → Homey control.
- The former Pi energy-state publisher was retired from production and removed from the repository on 2026-09-26 after the private Pi-hosted Frontend V2 cutover to `GET /web/state/current`.

No energy-state publication service or timer is supported here.
