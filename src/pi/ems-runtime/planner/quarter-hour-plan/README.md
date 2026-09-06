# Quarter-hour shadow planner

This directory contains the Raspberry Pi 24-hour / 15-minute shadow planner and its website publisher.

Current behaviour is documented centrally in [`docs/pi-planner.md`](../../../../../docs/pi-planner.md).

## Components

- `build_shadow_load_plan.py` builds the aligned 96-slot combined plan from PV, Quatt, base load, warm water and price inputs and includes Tesla opportunity planning.
- `build_website_shadow.py` converts the Pi plan into the website shadow schema.

## Tesla policy (v0.6)

Tesla planning is currently **opportunity-only** and performs no physical writes. Opportunity charging does not require a kWh goal. It uses forecast PV surplus, START7 / RUN6 electrical semantics and a 16 A opportunity maximum.

Future availability uses the normal weekly presence forecast: Thursday from 18:00 through Monday before 08:00 is expected home; Monday from 08:00 through Thursday before 18:00 is expected away. A live `connected=true` signal may override this only for the first two hours of the planning horizon so that a current connection is not projected across the whole next day.

Deadline planning is not yet implemented in this Pi component.

## Change discipline

Any behavioural change in this directory must update this README and/or `docs/pi-planner.md` in the same change set.