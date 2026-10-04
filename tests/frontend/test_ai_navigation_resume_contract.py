#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "frontend/ai/render/ai.js"


def main():
    source = JS.read_text(encoding="utf-8")

    required = [
        "sessionStorage",
        "requestId",
        "/agent/result?",
        "resumePending",
        "pagehide",
        "messages.scrollTo",
    ]
    missing = [item for item in required if item not in source]
    assert not missing, "missing AI navigation-resume markers: " + ", ".join(missing)

    assert "scrollIntoView" not in source
    assert "state.pending" in source
    assert "addUser:false" in source

    print("PASS: AI navigation resume frontend contract")


if __name__ == "__main__":
    main()
