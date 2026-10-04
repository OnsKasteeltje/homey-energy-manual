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
        "recentConversationContext",
        "conversationContext",
        "MAX_CONTEXT_MESSAGES",
        "MAX_CONTEXT_MESSAGE_CHARS",
    ]
    missing = [item for item in required if item not in source]
    assert not missing, "missing AI navigation-resume markers: " + ", ".join(missing)

    assert "scrollIntoView" not in source
    assert "state.pending" in source
    assert "addUser:false" in source
    assert "conversationContext:context" in source
    assert "item.requestId!==excludeRequestId" in source
    assert 'item.text.startsWith("Analyse niet beschikbaar:")' in source

    print("PASS: AI navigation resume frontend contract")


if __name__ == "__main__":
    main()
