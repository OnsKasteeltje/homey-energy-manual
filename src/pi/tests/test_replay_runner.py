from __future__ import annotations

import json
from pathlib import Path

from replay_runner import run_replay


FIXTURES = Path(__file__).parent / "fixtures"


def test_integrated_replay_passes() -> None:
    payload = json.loads((FIXTURES / "replay_ev_deadline_publish.json").read_text())
    report = run_replay(payload)

    assert report["status"] == "PASS"
    assert report["actual"]["ev_semantics"]["mode"] == "DEADLINE"
    assert report["actual"]["publisher"]["decision"]["reason"] == "REVISION_EVENT"
    assert all(check["pass"] for check in report["checks"])


def test_integrated_replay_fails_on_expected_mismatch() -> None:
    payload = json.loads((FIXTURES / "replay_ev_deadline_publish.json").read_text())
    payload["expected"]["ev_semantics"]["mode"] = "HOLD"

    report = run_replay(payload)

    assert report["status"] == "FAIL"
    failed = [check for check in report["checks"] if not check["pass"]]
    assert len(failed) == 1
    assert failed[0]["path"] == "ev_semantics.mode"
