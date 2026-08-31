from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ems.ev_semantics import EvSemanticInput, build_ev_control
from ems.replay import replay_projection, state_from_fixture
from ems.ww_semantics import WwAdapterInput, build_ww_adapter
from publisher import build_payload, decide_publish


def _dt(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value.replace("Z", "+00:00"))


def run_replay(payload: dict[str, Any]) -> dict[str, Any]:
    now = _dt(payload["replay_at"])
    if now is None:
        raise ValueError("replay_at is required")

    state_payload = payload["state"]
    state = state_from_fixture(state_payload)
    core = replay_projection(state, now)

    ev_cfg = payload["ev_semantics"]
    ev = build_ev_control(
        EvSemanticInput(
            decision_mode=ev_cfg["decision_mode"],
            flex_W=ev_cfg["flex_W"],
            charger_available=ev_cfg["charger_available"],
            deadline_active=ev_cfg["deadline_active"],
            core_revision=ev_cfg["core_revision"],
        )
    )

    ww_cfg = payload.get("ww_adapter")
    ww: dict[str, Any] | None = None
    if ww_cfg is not None:
        ww = build_ww_adapter(
            WwAdapterInput(
                schema=ww_cfg["schema"],
                valid=ww_cfg["valid"],
                device_writes=ww_cfg["device_writes"],
                source_revision=ww_cfg.get("source_revision"),
                target_present=ww_cfg["target_present"],
                target_on=ww_cfg.get("target_on"),
                source_action=ww_cfg.get("source_action"),
            )
        )

    pub_cfg = payload["publisher"]
    decision = decide_publish(
        pub_cfg["public_state"],
        pub_cfg["authoritative_state"],
        last_published_revision=pub_cfg.get("last_published_revision"),
        last_publish_at=_dt(pub_cfg.get("last_publish_at")),
        now=now,
    )
    publisher: dict[str, Any] = {"decision": asdict(decision)}
    if decision.due:
        publisher["payload"] = build_payload(pub_cfg["public_state"], decision, now=now)

    actual = {"core": core, "ev_semantics": ev, "ww_adapter": ww, "publisher": publisher}
    expected = payload.get("expected", {})
    checks: list[dict[str, Any]] = []

    def check(path: str, actual_value: Any, expected_value: Any) -> None:
        checks.append(
            {
                "path": path,
                "expected": expected_value,
                "actual": actual_value,
                "pass": actual_value == expected_value,
            }
        )

    for key, value in expected.get("core", {}).items():
        check(f"core.{key}", core.get(key), value)
    for key, value in expected.get("ev_semantics", {}).items():
        check(f"ev_semantics.{key}", ev.get(key), value)
    if ww is not None:
        for key, value in expected.get("ww_adapter", {}).items():
            if key == "command_value":
                check("ww_adapter.command.value", ww["command"].get("value"), value)
            else:
                check(f"ww_adapter.{key}", ww.get(key), value)
    for key, value in expected.get("publisher", {}).items():
        check(f"publisher.decision.{key}", publisher["decision"].get(key), value)

    passed = all(item["pass"] for item in checks) if checks else False
    return {
        "schema": "PI_EMS_REPLAY_REPORT_V0.2",
        "fixture_id": payload.get("fixture_id", "UNKNOWN"),
        "replay_at": now.isoformat(),
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "actual": actual,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an offline deterministic EMS replay fixture")
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    report = run_replay(fixture)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
