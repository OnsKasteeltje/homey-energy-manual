# Heating state

Canonical Pi interpretation layer for room-heating state.

## Heating Room Model V0.1

`build_heating_room_model.py` combines the canonical read-only Honeywell snapshots:

- `EMS_HONEYWELL_SCHEDULE_V0.2`
- `EMS_HONEYWELL_STATE_V0.2`

and emits `EMS_HEATING_ROOM_MODEL_V0.1`.

The builder is deliberately pure with respect to external systems: it does not contact Honeywell, Homey or devices and contains no PV/preheat or actuator decision.

The model keeps the raw weekly schedule separate from the **effective Honeywell target**. `follow_schedule` may use the scheduled transition only when the current vendor target is aligned with the active schedule and the Honeywell system is in normal `auto` mode. `temporary_override` and `permanent_override` make the current vendor target authoritative for comfort demand and block EMS preheat advancement while the override is active. Temporary override expiry is preserved as `overrideUntil`; the weekly schedule remains available as reference and resumes only after Honeywell reports schedule-following state again.

All switchpoint timestamps at the EMS boundary are offset-aware and normalized to `Europe/Amsterdam`. Invalid schemas, room-key mismatches, duplicate keys, non-OK schedules, missing values and naive timestamps fail closed.

Example runtime invocation:

```bash
python3 services/pi/state/heating/build_heating_room_model.py \
  --schedule /home/jeroen/ems/runtime/tools/honeywell/output/honeywell-schedule.json \
  --state /home/jeroen/ems/runtime/tools/honeywell/output/honeywell-state.json \
  --output /home/jeroen/ems/runtime/state/heating-room-model.json
```

The output path is runtime state and must not be treated as a GitHub source of truth.
