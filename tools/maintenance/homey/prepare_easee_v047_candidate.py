#!/usr/bin/env python3
"""Prepare (do not deploy) the pinned Homey EV v0.4.7 token-bundle candidate.

Read-only Homey interaction: one targeted Advanced Flow read. No Easee calls,
Homey Logic writes, flow updates, or physical charging commands.
"""
import copy
import json
import re
from pathlib import Path

from homey_flow_deploy import read_live

REPO = Path(__file__).resolve().parents[3]
FLOW_ID = "fea23193-a03f-49dd-9780-7e72ee48747d"
CODE_CARD_ID = "10a00000-0000-4000-8000-000000000002"
REGISTRY = Path("/home/jeroen/ems/data/easee-homey-token-variable-ids.json")
BUNDLE_KEY = "EM2_Easee_Token_Bundle_V1"
PLACEHOLDER = "__EM2_EASEE_BUNDLE_ID__"
OUTPUT = Path("/home/jeroen/ems/data/deploy/easee-v047-candidate.json")
OLD_SOURCE = REPO / "apps/homey/control/ev/ev-power-v0.4.6.off-zero-idempotent.js"
NEW_SOURCE = REPO / "apps/homey/control/ev/ev-power-v0.4.7.atomic-easee-tokens.js"

def main():
    ids = json.loads(REGISTRY.read_text(encoding="utf-8"))
    bundle_id = str(ids.get(BUNDLE_KEY) or "").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}", bundle_id):
        raise RuntimeError("BUNDLE_ID_NOT_COMMISSIONED: run token bootstrap first")

    old = OLD_SOURCE.read_text(encoding="utf-8")
    candidate_source = NEW_SOURCE.read_text(encoding="utf-8")
    if candidate_source.count(PLACEHOLDER) != 1:
        raise RuntimeError("INVALID_BUNDLE_PLACEHOLDER_COUNT")
    candidate_source = candidate_source.replace(PLACEHOLDER, bundle_id)
    if PLACEHOLDER in candidate_source:
        raise RuntimeError("UNRESOLVED_PLACEHOLDER")

    live = read_live(FLOW_ID)
    if live.get("id") != FLOW_ID or live.get("broken") or not live.get("enabled"):
        raise RuntimeError("LIVE_FLOW_NOT_READY")
    card = (live.get("cards") or {}).get(CODE_CARD_ID)
    if not card or card.get("id") != "homey:app:com.athom.homeyscript:runCode_v2":
        raise RuntimeError("LIVE_SCRIPT_CARD_MISMATCH")
    if card.get("args", {}).get("code") != old:
        raise RuntimeError("LIVE_SOURCE_DRIFT: do not overwrite unexpected Homey code")
    if "v0.4.6" not in live["name"]:
        raise RuntimeError("LIVE_VERSION_MISMATCH")

    candidate = copy.deepcopy(live)
    candidate["name"] = live["name"].replace(
        "v0.4.6 OFF-ZERO-IDEMPOTENT", "v0.4.7 ATOMIC-TOKENS"
    )
    candidate["cards"][CODE_CARD_ID]["args"]["code"] = candidate_source

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(candidate, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    OUTPUT.chmod(0o600)
    print("PASS: v0.4.7 candidate prepared; no Homey writes")
    print("Candidate:", OUTPUT)
    print("Flow ID:", FLOW_ID)
    print("Next: run the existing controlled Homey deployer in DRY-RUN mode")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
