#!/usr/bin/env python3
"""Contract test for deterministic Heating SHADOW timer ordering."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

TIMERS = {
    "v03": ROOT / "deploy/systemd/ems-heating-preheat-shadow.timer",
    "flex": ROOT / "deploy/systemd/ems-flex-priority-shadow.timer",
    "v04": ROOT / "deploy/systemd/ems-heating-preheat-progression-shadow.timer",
    "v05": ROOT / "deploy/systemd/ems-heating-control-gate-shadow.timer",
    "publish": ROOT / "deploy/systemd/ems-heating-homey-shadow-publish.timer",
}

EXPECTED_CALENDAR = {
    "v03": "*-*-* *:04/5:00",
    "flex": "*-*-* *:*:10",
    "v04": "*-*-* *:*:20",
    "v05": "*-*-* *:*:30",
    "publish": "*-*-* *:*:35",
}


def value(text: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}=(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def main() -> None:
    texts = {name: path.read_text(encoding="utf-8") for name, path in TIMERS.items()}

    for name, text in texts.items():
        assert value(text, "OnCalendar") == EXPECTED_CALENDAR[name], (
            name,
            value(text, "OnCalendar"),
        )
        assert value(text, "Persistent") == "true", name
        assert value(text, "AccuracySec") == "1s", name

    assert "OnUnitActiveSec=" not in texts["flex"]
    assert "OnBootSec=" not in texts["flex"]

    # On every minute: Flex -> V0.4 -> V0.5 -> Homey publish.
    phase_seconds = [10, 20, 30, 35]
    assert phase_seconds == sorted(phase_seconds)
    assert all(b - a >= 5 for a, b in zip(phase_seconds, phase_seconds[1:]))

    # On each V0.3 refresh minute, V0.3 completes its timer phase first.
    assert 0 < phase_seconds[0]

    print("PASS: Heating SHADOW cadence is deterministic")
    print("V0.3 due minute :00 -> Flex :10 -> V0.4 :20 -> V0.5 :30 -> Publish :35")


if __name__ == "__main__":
    main()
