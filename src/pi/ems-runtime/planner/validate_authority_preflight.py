#!/usr/bin/env python3
import argparse, json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone


def load(path):
    return json.loads(Path(path).read_text())


def load_source(spec):
    """Load JSON from a filesystem path or git ref:path spec."""
    if ":" in spec and not spec.startswith("/"):
        ref, path = spec.split(":", 1)
        raw = subprocess.check_output(["git", "show", f"{ref}:{path}"], text=True)
        return json.loads(raw)
    return load(spec)


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


def unwrap_dynamic_plan(doc):
    if isinstance(doc, dict) and isinstance(doc.get("plan"), dict):
        candidate = doc["plan"]
        if candidate.get("schema") == "EMS_PI_DYNAMIC_ENERGY_PLAN_24H_V0.1":
            return doc, candidate
    return None, doc


def extract_slots(plan):
    if not isinstance(plan, dict):
        return None
    for key in ("slots", "quarterHours", "actions"):
        value = plan.get(key)
        if isinstance(value, list):
            return value
    nested = plan.get("plan")
    if isinstance(nested, dict):
        for key in ("slots", "quarterHours", "actions"):
            value = nested.get(key)
            if isinstance(value, list):
                return value
    return None


def main():
    ap = argparse.ArgumentParser(description="Read-only preflight for Homey -> Pi planner authority cutover.")
    ap.add_argument("--authority", default="/home/jeroen/ems/runtime/planner/control-authority.json")
    ap.add_argument("--selector", default="/home/jeroen/ems/runtime/planner/authority-selector-policy.json")
    ap.add_argument("--pi-plan", default="origin/main:docs/data/energy-planner-shadow-dynamic.json")
    ap.add_argument("--ev-status", default="origin/main:docs/data/ev-control-status.json")
    ap.add_argument("--energy-state", default="origin/main:docs/data/energy-state-v2.json")
    ap.add_argument("--max-plan-age-sec", type=int, default=1200)
    ap.add_argument("--max-state-age-sec", type=int, default=1200)
    args = ap.parse_args()

    failures = []
    authority = load(args.authority)
    selector = load(args.selector)
    plan_doc = load_source(args.pi_plan)
    ev = load_source(args.ev_status)
    state = load_source(args.energy_state)
    wrapper, plan = unwrap_dynamic_plan(plan_doc)

    print(f"SOURCE planner={args.pi_plan}")
    print(f"SOURCE ev={args.ev_status}")
    print(f"SOURCE state={args.energy_state}")

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

    mode = plan.get("controlMode") if isinstance(plan, dict) else None
    ro = plan.get("readOnly") if isinstance(plan, dict) else None
    physical = plan.get("physicalWritePerformed") if isinstance(plan, dict) else None
    wrapper_observe = True if wrapper is None else (
        wrapper.get("observabilityOnly") is True and wrapper.get("controlImpact") == "NONE"
    )
    shadow_ok = mode == "PURE_SHADOW" and ro is True and physical is False and wrapper_observe
    check(shadow_ok, "pi_plan_shadow_only",
          f"controlMode={mode}, readOnly={ro}, physicalWritePerformed={physical}, wrapperObserveOnly={wrapper_observe}", failures)

    generated = None
    if isinstance(plan, dict):
        generated = plan.get("generatedAt") or plan.get("publishedAt")
    if not generated and isinstance(wrapper, dict):
        generated = wrapper.get("generatedAt") or wrapper.get("publishedAt")
    age = iso_age_seconds(generated)
    fresh = age is not None and age <= args.max_plan_age_sec
    check(fresh, "pi_plan_fresh",
          f"generatedAt={generated}, ageSec={None if age is None else round(age)}", failures)

    slots = extract_slots(plan)
    slot_count = len(slots) if isinstance(slots, list) else None
    check(slot_count == 96, "pi_plan_96_slots", f"slots={slot_count}", failures)

    check(ev.get("coherent") is True, "ev_chain_coherent",
          f"coherent={ev.get('coherent')}", failures)
    health = ev.get("deviceHealth", {})
    health_safe = health.get("status") == "OK" and health.get("controlSafe") is True
    check(health_safe, "ev_device_health_safe",
          f"status={health.get('status')}, reason={health.get('reason')}", failures)
    check(ev.get("gate", {}).get("status") == "PASS", "ev_gate_pass",
          f"gate={ev.get('gate', {}).get('status')}", failures)
    check(ev.get("actuator", {}).get("live") is True, "ev_actuator_live",
          f"live={ev.get('actuator', {}).get('live')}", failures)
    check(ev.get("targetW") == 0 and ev.get("requestedA") == 0,
          "safe_zero_ev_start",
          f"targetW={ev.get('targetW')}, requestedA={ev.get('requestedA')}", failures)

    meta = state.get("meta", {}) if isinstance(state, dict) else {}
    state_generated = meta.get("generated_at") or meta.get("heartbeat_at")
    state_age = iso_age_seconds(state_generated)
    check(state_age is not None and state_age <= args.max_state_age_sec,
          "energy_state_fresh",
          f"generatedAt={state_generated}, ageSec={None if state_age is None else round(state_age)}", failures)

    hot = state.get("hot_water", {}) if isinstance(state, dict) else {}
    ww = hot.get("control", {}) if isinstance(hot, dict) else {}
    state_rev = meta.get("state_revision")
    ww_rev = ww.get("sourceRevision")
    check(ww.get("schema") == "EM2_CONTROL_WW_V0.11" and ww_rev == state_rev,
          "ww_revision_aligned",
          f"schema={ww.get('schema')}, wwRev={ww_rev}, stateRev={state_rev}", failures)
    check(ww.get("readOnly") is True and ww.get("safety", {}).get("physicalWritePerformed") is False,
          "ww_core_shadow_safe",
          f"readOnly={ww.get('readOnly')}, physicalWritePerformed={ww.get('safety', {}).get('physicalWritePerformed')}", failures)
    boiler_on = hot.get("boiler_on")
    boiler_w = hot.get("boiler_power_w")
    safe_boiler_off = boiler_on is False and isinstance(boiler_w, (int, float)) and boiler_w < 100
    check(safe_boiler_off, "safe_zero_ww_start",
          f"boilerOn={boiler_on}, boilerPowerW={boiler_w}", failures)
    check(ww.get("action") in ("HOLD", "OFF"), "ww_safe_core_action",
          f"action={ww.get('action')}, priority={ww.get('priority')}", failures)

    print()
    if failures:
        print("CUTOVER_PREP: FAIL")
        print("Blocking checks:", ", ".join(failures))
        return 2
    print("CUTOVER_PREP: PASS")
    print("No authority was changed. This script is read-only.")
    print("NOTE: WW checks validate published safe state/revision alignment; live Homey WW gate/actuator status must still be verified before physical cutover.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
