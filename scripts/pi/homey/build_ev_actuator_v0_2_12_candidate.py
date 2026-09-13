#!/usr/bin/env python3
"""Build EV Actuator v0.2.12 candidate from the deployed v0.2.11 Advanced Flow.

This is a wiring-only fix. It performs no Homey calls.

Changes:
- production root card no longer forces EM2_EV_Actuator_Live_Enabled=false;
  it sets the live flag true before entering the actuator path.
- session-entry condition no longer hardcodes actuator schema v0.2.9;
  it accepts the current actuator schema and both normal and degraded
  deadline-ready statuses.

All safety decisions remain inside the v0.2.11 actuator and post-session code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

FLOW_ID_DEFAULT = "fea23193-a03f-49dd-9780-7e72ee48747d"
LIVE_SET_CARD_ID = "10a00000-0000-4000-8000-000000000005"
SESSION_READY_CARD_ID = "10a00000-0000-4000-8000-000000000007"
MAIN_CARD_ID = "10a00000-0000-4000-8000-000000000002"
SESSION_CARD_ID = "10a00000-0000-4000-8000-00000000000f"
LIVE_VAR_ID = "8d47e98d-e4bc-4f47-8c02-c2aca7f7a978"
STATUS_VAR_ID = "ea1f8a44-2f6c-490e-9b86-bae761886cf9"
EXPECTED_BASELINE = "EM2_EV_ACTUATOR_V0.2.11"

SESSION_READY_CODE = r'''const [l,s]=await Promise.all([
  Homey.logic.getVariable({id:'8d47e98d-e4bc-4f47-8c02-c2aca7f7a978'}),
  Homey.logic.getVariable({id:'ea1f8a44-2f6c-490e-9b86-bae761886cf9'})
]);
let x=null;try{x=JSON.parse(String(s?.value??''));}catch{}
const a=Number(x?.targetA);
const schemaOK=String(x?.schema||'').startsWith('EM2_EV_ACTUATOR_V0.2.');
const statusOK=['READY_SESSION_CONTROL','READY_SESSION_CONTROL_DEGRADED_DEADLINE_AUTHORITY'].includes(String(x?.status||''));
return l?.value===true&&schemaOK&&statusOK&&Number.isInteger(a)&&a>=6&&a<=16;'''


def load_flow(path: Path, flow_id: str):
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and flow_id in raw:
        return raw[flow_id]
    if isinstance(raw, dict) and raw.get("id") == flow_id:
        return raw
    raise SystemExit(f"flow not found: {flow_id}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="/tmp/ev-actuator-live.json")
    ap.add_argument("--output", default="/tmp/ev-actuator-v0.2.12-candidate.json")
    ap.add_argument("--flow-id", default=FLOW_ID_DEFAULT)
    args = ap.parse_args()

    flow = load_flow(Path(args.input), args.flow_id)
    if flow.get("enabled") is not True:
        raise SystemExit("refusing: live baseline flow is not enabled")
    if flow.get("broken") is True:
        raise SystemExit("refusing: live baseline flow is broken")

    cards = flow.get("cards") or {}
    for cid in (LIVE_SET_CARD_ID, SESSION_READY_CARD_ID, MAIN_CARD_ID, SESSION_CARD_ID):
        if cid not in cards:
            raise SystemExit(f"required card missing: {cid}")

    main_code = str((cards[MAIN_CARD_ID].get("args") or {}).get("code", ""))
    session_code = str((cards[SESSION_CARD_ID].get("args") or {}).get("code", ""))
    if EXPECTED_BASELINE not in main_code or EXPECTED_BASELINE not in session_code:
        raise SystemExit("refusing: expected deployed v0.2.11 actuator baseline not found")

    live_card = cards[LIVE_SET_CARD_ID]
    if live_card.get("id") != "homey:manager:logic:variable_set_boolean":
        raise SystemExit("refusing: live setter card has unexpected type")
    live_args = live_card.get("args") or {}
    if (live_args.get("variable") or {}).get("id") != LIVE_VAR_ID:
        raise SystemExit("refusing: live setter points to unexpected variable")
    if live_args.get("value") is not False:
        raise SystemExit("refusing: baseline live setter is not the known false cutover artifact")
    live_args["value"] = True

    ready_card = cards[SESSION_READY_CARD_ID]
    if ready_card.get("id") != "homey:app:com.athom.homeyscript:runCode_v2":
        raise SystemExit("refusing: session-ready card has unexpected type")
    old_ready = str((ready_card.get("args") or {}).get("code", ""))
    if "EM2_EV_ACTUATOR_V0.2.9" not in old_ready:
        raise SystemExit("refusing: expected hardcoded v0.2.9 session gate not found")
    ready_card["args"]["code"] = SESSION_READY_CODE

    flow["name"] = "EM v2 | 60 Actuator | EV Power v0.2.12 LIVE WIRING + DEADLINE GATE AUTHORITY"

    out = Path(args.output)
    out.write_text(json.dumps(flow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"candidate={out}")
    print(f"flow_id={args.flow_id}")
    print(f"name={flow['name']}")
    print(f"enabled={flow.get('enabled')} broken={flow.get('broken')}")
    print(f"live_set_card={LIVE_SET_CARD_ID} false -> true")
    print(f"session_ready_card={SESSION_READY_CARD_ID} v0.2.9 hardcode -> version-independent v0.2.x contract")
    print("accepted_ready_statuses=READY_SESSION_CONTROL,READY_SESSION_CONTROL_DEGRADED_DEADLINE_AUTHORITY")
    print("actuator_logic=v0.2.11 unchanged")
    print("homey_calls=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
