#!/usr/bin/env python3

"""Export a privacy-safe Honeywell schedule snapshot for the EMS website.

This is a derived/public view of output/honeywell-schedule.json. It does not call
Honeywell and does not create a second source of truth. The canonical source stays
the read-only Honeywell schedule collector.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from honeywell_common import ROOT, atomic_write_json

SOURCE = ROOT / "output" / "honeywell-schedule.json"


def build_public_payload(source: dict) -> dict:
    if source.get("schema") != "EMS_HONEYWELL_SCHEDULE_V0.2":
        raise SystemExit(
            "ERROR: expected EMS_HONEYWELL_SCHEDULE_V0.2, got "
            + str(source.get("schema"))
        )

    rooms = []
    for zone in source.get("zones", []):
        if zone.get("scheduleStatus") != "OK" or not zone.get("weeklySchedule"):
            continue
        rooms.append(
            {
                "key": zone["key"],
                "displayName": zone["displayName"],
                "sourceName": zone.get("sourceName"),
                "weeklySchedule": zone["weeklySchedule"],
            }
        )

    if not rooms:
        raise SystemExit("ERROR: no valid Honeywell room schedules available")

    return {
        "schema": "EMS_PUBLIC_HEATING_SCHEDULE_V0.1",
        "generatedAt": source["generatedAt"],
        "source": "HONEYWELL_SCHEDULE_COLLECTOR",
        "readOnly": True,
        "baselineAuthority": "HONEYWELL",
        "rooms": rooms,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help="Target website JSON, e.g. /home/jeroen/ems/repo/homey-energy-manual/docs/data/honeywell-schedule.json",
    )
    args = parser.parse_args()

    try:
        source = json.loads(SOURCE.read_text())
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot read {SOURCE}: {exc}") from exc

    payload = build_public_payload(source)
    atomic_write_json(args.target, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
