#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
from datetime import datetime, timezone

def load(path):
    return json.loads(Path(path).read_text())

def iso_age_seconds(value):
    if not value:
        return None
    s = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())

def check(ok, name, detail, failures):
    status = "PASS" if ok else "FAIL"
    print(f"{status:4}  {name}: {detail}")
    if not ok:
        failures.append(name)

def main():
    ap = argparse.ArgumentParser(description="Read-only preflight for Homey -> Pi planner authority cutover.")
    ap.add_argument("--authority", default="/home/jeroen/ems/runtime/planner/control-authority.json")
    ap.add_argument("--selector", default="/home/jeroen/ems/runtime/planner/authority-selector-policy.json")
    ap.add_argument("--pi-plan", default="/home/jeroen/ems/data/energy-planner-shadow.json")
    ap.add_argument("--ev-status", default="/home/jeroen/ems/repo/homey-energy-manual/docs/data/ev-control-status.json")
    ap.add_argument("--max-plan-age-sec", type=int, default=1200)
    args = ap.parse_args()

    failures = []
    authority = load(args.authority)
    selector = load(args.selector)
    plan = load(args.pi_plan)
    ev = load(args.ev_status)

    check(authority.get("plannerOwner") == "HOMEY", "authority_homey",
          f"plannerOwner={authority.get('plannerOwner')}", failures)
    check(authority.get("manualCutoverAuthorized") is False, "manual_cutover_locked",
          f"manualCutoverAuthorized={authority.get('manualCutoverAuthorized')}", failures)
    check(authority.get("piBridgeEnabled") is False, "pi_bridge_disabled",
          f"piBridgeEnabled={authority.get('piBridgeEnabled')}", failures)
    check(selector.get("currentAuthority") == "HOMEY", "selector_homey",
          f"currentAuthority={selector.get('currentAuthority')}", failures)
    check(selector.get("invariants", {}).get("singleActiveIntentProducer") is True,
          "single_producer_invariant", "required=true", failures)
    check(selector.get("invariants", {}).get("noDirectPiDeviceWrites") is True,
          "no_direct_pi_writes", "required=true", failures)

    contract_ok = (
        authority.get("contractMode") == "FIXED"
        and authority.get("contractId") == "ENGIE_3Y_2026_2029"
        and authority.get("dynamicPricingProduction") is False
        and authority.get("autoContractSwitch") is False
    )
    check(contract_ok, "fixed_contract_guard",
          f"{authority.get('contractMode')} / {authority.get('contractId')}", failures)

    mode = plan.get("controlMode")
    ro = plan.get("readOnly")
    writes = plan.get("deviceWrites")
    check(mode == "PURE_SHADOW" and ro is True and writes is False,
          "pi_plan_shadow_only",
          f"controlMode={mode}, readOnly={ro}, deviceWrites={writes}", failures)

    generated = plan.get("generatedAt") or plan.get("publishedAt")
    age = iso_age_seconds(generated)
    fresh = age is not None and age <= args.max_plan_age_sec
    check(fresh, "pi_plan_fresh",
          f"generatedAt={generated}, ageSec={None if age is None else round(age)}", failures)

    slots = plan.get("slots")
    if slots is None:
        slots = plan.get("quarterHours")
    if slots is None:
        slots = plan.get("plan", {}).get("slots") if isinstance(plan.get("plan"), dict) else None
    slot_count = len(slots) if isinstance(slots, list) else None
    check(slot_count == 96, "pi_plan_96_slots", f"slots={slot_count}", failures)

    check(ev.get("coherent") is True, "ev_chain_coherent",
          f"coherent={ev.get('coherent')}", failures)
    check(ev.get("gate", {}).get("status") == "PASS", "ev_gate_pass",
          f"gate={ev.get('gate', {}).get('status')}", failures)
    check(ev.get("actuator", {}).get("live") is True, "ev_actuator_live",
          f"live={ev.get('actuator', {}).get('live')}", failures)
    check(ev.get("targetW") == 0 and ev.get("requestedA") == 0,
          "safe_zero_ev_start",
          f"targetW={ev.get('targetW')}, requestedA={ev.get('requestedA')}", failures)

    print()
    if failures:
        print("CUTOVER_PREP: FAIL")
        print("Blocking checks:", ", ".join(failures))
        return 2
    print("CUTOVER_PREP: PASS")
    print("No authority was changed. This script is read-only.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
