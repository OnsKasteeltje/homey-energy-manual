# Heating state

Canonical Pi interpretation layer for room-heating state.

## Heating Room Model V0.1

`build_heating_room_model.py` combines the canonical read-only Honeywell snapshots:

- `EMS_HONEYWELL_SCHEDULE_V0.2`
- `EMS_HONEYWELL_STATE_V0.2`

and emits `EMS_HEATING_ROOM_MODEL_V0.1`.

The builder is deliberately pure with respect to external systems: it does not contact Honeywell, Homey or devices and contains no PV/preheat or actuator decision.

The actual Honeywell target from the state snapshot remains separate from the scheduled baseline. Transition direction is derived only from the scheduled current and next switchpoints, so a temporary/manual override cannot rewrite the comfort baseline.

All switchpoint timestamps at the EMS boundary are offset-aware and normalized to `Europe/Amsterdam`. Invalid schemas, room-key mismatches, duplicate keys, non-OK schedules, missing values and naive timestamps fail closed.

Example runtime invocation:

```bash
python3 services/pi/state/heating/build_heating_room_model.py \
  --schedule /home/jeroen/ems/runtime/tools/honeywell/output/honeywell-schedule.json \
  --state /home/jeroen/ems/runtime/tools/honeywell/output/honeywell-state.json \
  --output /home/jeroen/ems/runtime/state/heating-room-model.json
```

The output path is runtime state and must not be treated as a GitHub source of truth.
