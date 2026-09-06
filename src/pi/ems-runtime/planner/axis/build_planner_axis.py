#!/usr/bin/env python3

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUTPUT = Path("/home/jeroen/ems/data/planner-axis.json")
SLOT_MINUTES = 15
SLOT_COUNT = 96


def floor_quarter(dt):
    seconds = int(dt.timestamp())
    return datetime.fromtimestamp(
        seconds - (seconds % (SLOT_MINUTES * 60)),
        tz=timezone.utc,
    )


start = floor_quarter(datetime.now(timezone.utc))

slots = []
for i in range(SLOT_COUNT):
    dt = start + timedelta(minutes=i * SLOT_MINUTES)
    slots.append(
        dt.isoformat(timespec="seconds").replace("+00:00", "Z")
    )

document = {
    "schema": "EMS_PI_PLANNER_AXIS_V0.1",
    "generated_at": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
    "resolution_minutes": SLOT_MINUTES,
    "slot_count": SLOT_COUNT,
    "start_utc": slots[0],
    "end_utc": slots[-1],
    "slots": slots,
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

tmp = OUTPUT.with_suffix(".tmp")
with tmp.open("w") as f:
    json.dump(document, f, indent=2)

tmp.replace(OUTPUT)

print(f"PASS: planner axis built")
print(f"slots : {len(slots)}")
print(f"first : {slots[0]}")
print(f"last  : {slots[-1]}")
print(f"output: {OUTPUT}")
