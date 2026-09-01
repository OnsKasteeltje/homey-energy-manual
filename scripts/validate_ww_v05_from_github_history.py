#!/usr/bin/env python3
"""Validate the WW Planner v0.5 daylight ON route from GitHub history only.

No Homey API/device access and no physical writes. The validator reconstructs
15-minute Planner and published Core snapshots from repository commit history
and reports PASS/FAIL/NOT_OBSERVED for the evidence needed to validate:

1. Planner wwTargetW=1900 + PV_PREFERRED.
2. Core plannerFresh=true + plannerCompatible=true at that quarter.
3. Sufficient current P1 export/flex budget for the 1900 W WW target.
4. Core plannerPvConfirmed=true.
5. EM2_Control_WW ON intent caused by Planner/PV.
6. remainingFallbackMin decreases and goalReachedToday eventually becomes true.
7. Core physicalWritePerformed=false.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = "OnsKasteeltje/homey-energy-manual"
STATE_PATH = "docs/data/energy-state-v2.json"
PLANNER_PATH = "docs/data/energy-planner-shadow.json"
BOILER_W = 1900.0


def get_json(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ems-ww-v05-history-validator"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def iso_z(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_ts(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def quarter_floor(dt):
    return dt.replace(minute=(dt.minute // 15) * 15, second=0, microsecond=0)


def commits_for(path, start, end):
    q = urllib.parse.urlencode({"path": path, "since": iso_z(start), "until": iso_z(end), "per_page": 100})
    return get_json(f"https://api.github.com/repos/{REPO}/commits?{q}")


def file_at(path, sha):
    return get_json(f"https://raw.githubusercontent.com/{REPO}/{sha}/{path}")


def first_action_for_quarter(snapshot, qstart):
    actions = (((snapshot or {}).get("plan") or {}).get("plan") or {}).get("actions") or []
    for action in actions:
        try:
            if quarter_floor(parse_ts(action.get("start"))) == qstart:
                return action
        except Exception:
            pass
    return None


def status(name, result, evidence=None):
    return {"check": name, "status": result, "evidence": evidence or {}}


def validate(date_local, utc_offset_hours=2):
    local_start = datetime.fromisoformat(date_local).replace(tzinfo=timezone(timedelta(hours=utc_offset_hours)))
    start = local_start.astimezone(timezone.utc)
    end = (local_start + timedelta(days=1)).astimezone(timezone.utc) - timedelta(microseconds=1)

    state_commits = commits_for(STATE_PATH, start, end)
    planner_commits = commits_for(PLANNER_PATH, start, end)

    state_by_q = {}
    for commit in reversed(state_commits):
        snap = file_at(STATE_PATH, commit["sha"])
        generated = parse_ts((snap.get("meta") or {}).get("generated_at") or commit["commit"]["committer"]["date"])
        state_by_q[quarter_floor(generated)] = snap

    planner_by_q = {}
    for commit in reversed(planner_commits):
        snap = file_at(PLANNER_PATH, commit["sha"])
        generated = parse_ts(snap.get("generatedAt") or snap.get("publishedAt") or commit["commit"]["committer"]["date"])
        planner_by_q[quarter_floor(generated)] = snap

    candidate_quarters = []
    for q, planner in sorted(planner_by_q.items()):
        action = first_action_for_quarter(planner, q)
        if not action:
            continue
        target = ((action.get("targets") or {}).get("wwTargetW"))
        warm = str(action.get("warmWater") or "").upper()
        if target == 1900 and warm == "PV_PREFERRED":
            candidate_quarters.append((q, action))

    checks = []
    if candidate_quarters:
        q, action = candidate_quarters[0]
        checks.append(status("planner_pv_preferred_target", "PASS", {
            "quarter": iso_z(q), "warmWater": action.get("warmWater"),
            "wwTargetW": (action.get("targets") or {}).get("wwTargetW"),
            "pvForecastW": action.get("pvForecastW")
        }))
    else:
        checks.append(status("planner_pv_preferred_target", "NOT_OBSERVED"))

    matched_states = []
    for q, action in candidate_quarters:
        state = state_by_q.get(q)
        if state:
            matched_states.append((q, action, state))

    if candidate_quarters and not matched_states:
        checks.extend([
            status("core_planner_compatibility", "FAIL", {"reason": "candidate Planner quarter has no matching state snapshot"}),
            status("p1_export_sufficient", "FAIL", {"reason": "candidate Planner quarter has no matching state snapshot"}),
            status("planner_pv_confirmed", "FAIL", {"reason": "candidate Planner quarter has no matching state snapshot"}),
            status("ww_on_intent_planner_pv", "FAIL", {"reason": "candidate Planner quarter has no matching state snapshot"}),
        ])
    elif not candidate_quarters:
        checks.extend([
            status("core_planner_compatibility", "NOT_OBSERVED"),
            status("p1_export_sufficient", "NOT_OBSERVED"),
            status("planner_pv_confirmed", "NOT_OBSERVED"),
            status("ww_on_intent_planner_pv", "NOT_OBSERVED"),
        ])
    else:
        compat_pass = False
        export_pass = False
        confirmed_pass = False
        intent_pass = False
        compat_ev = export_ev = confirmed_ev = intent_ev = {}
        for q, action, state in matched_states:
            hot = state.get("hot_water") or {}
            control = hot.get("control") or {}
            guards = control.get("guards") or {}
            inputs = control.get("inputs") or {}
            safety = control.get("safety") or {}
            compat = guards.get("plannerFresh") is True and guards.get("plannerCompatible") is True
            flex = inputs.get("flexExportBudgetW")
            export_w = inputs.get("exportW")
            sufficient = isinstance(flex, (int, float)) and float(flex) >= BOILER_W
            confirmed = guards.get("plannerPvConfirmed") is True
            opportunity = str(control.get("opportunity") or "").upper()
            reason = str(control.get("reason") or "")
            action_name = str(control.get("action") or "").upper()
            planner_pv_intent = action_name == "BOILER_ON" and (opportunity == "PLANNER_PV_CONFIRMED" or "Planner PV" in reason)
            common = {"quarter": iso_z(q), "sourceRevision": control.get("sourceRevision")}
            if compat and not compat_pass:
                compat_pass, compat_ev = True, {**common, "plannerFresh": True, "plannerCompatible": True}
            if sufficient and not export_pass:
                export_pass, export_ev = True, {**common, "exportW": export_w, "flexExportBudgetW": flex, "requiredW": BOILER_W}
            if confirmed and not confirmed_pass:
                confirmed_pass, confirmed_ev = True, {**common, "plannerPvConfirmed": True}
            if planner_pv_intent and not intent_pass:
                intent_pass, intent_ev = True, {**common, "action": control.get("action"), "opportunity": control.get("opportunity"), "reason": reason, "physicalWritePerformed": safety.get("physicalWritePerformed")}
        checks.append(status("core_planner_compatibility", "PASS" if compat_pass else "FAIL", compat_ev))
        checks.append(status("p1_export_sufficient", "PASS" if export_pass else "FAIL", export_ev))
        checks.append(status("planner_pv_confirmed", "PASS" if confirmed_pass else "FAIL", confirmed_ev))
        checks.append(status("ww_on_intent_planner_pv", "PASS" if intent_pass else "FAIL", intent_ev))

    ordered_states = []
    for q, state in sorted(state_by_q.items()):
        hot = state.get("hot_water") or {}
        day = hot.get("day_state") or {}
        ordered_states.append((q, day))
    remaining = [(q, d.get("remainingFallbackMin")) for q, d in ordered_states if isinstance(d.get("remainingFallbackMin"), (int, float))]
    decreased = any(float(remaining[i][1]) < float(remaining[i-1][1]) for i in range(1, len(remaining)))
    goal_rows = [(q, d) for q, d in ordered_states if d.get("goalReachedToday") is True]
    if decreased and goal_rows:
        q, d = goal_rows[-1]
        checks.append(status("fallback_decreases_and_goal_reached", "PASS", {
            "goalQuarter": iso_z(q), "goalReachedToday": True,
            "remainingFallbackMin": d.get("remainingFallbackMin"),
            "observedRemainingSeries": [{"quarter": iso_z(x), "remainingFallbackMin": v} for x, v in remaining]
        }))
    elif remaining or goal_rows:
        checks.append(status("fallback_decreases_and_goal_reached", "FAIL", {
            "decreased": decreased, "goalObserved": bool(goal_rows),
            "observedRemainingSeries": [{"quarter": iso_z(x), "remainingFallbackMin": v} for x, v in remaining]
        }))
    else:
        checks.append(status("fallback_decreases_and_goal_reached", "NOT_OBSERVED"))

    safety_rows = []
    for q, state in sorted(state_by_q.items()):
        safety = (((state.get("hot_water") or {}).get("control") or {}).get("safety") or {})
        if "physicalWritePerformed" in safety:
            safety_rows.append((q, safety.get("physicalWritePerformed")))
    if safety_rows:
        all_false = all(value is False for _, value in safety_rows)
        checks.append(status("core_no_physical_writes", "PASS" if all_false else "FAIL", {
            "samples": len(safety_rows),
            "nonFalse": [{"quarter": iso_z(q), "physicalWritePerformed": value} for q, value in safety_rows if value is not False]
        }))
    else:
        checks.append(status("core_no_physical_writes", "NOT_OBSERVED"))

    result = {
        "schema": "EM2_WW_V05_GITHUB_HISTORY_VALIDATION_V0.1",
        "dateLocal": date_local,
        "method": "GITHUB_COMMIT_HISTORY_15_MIN_OBSERVATIONAL_VALIDATION",
        "homeyReads": 0,
        "physicalWrites": 0,
        "stateSnapshots": len(state_by_q),
        "plannerSnapshots": len(planner_by_q),
        "plannerPvPreferredCandidates": len(candidate_quarters),
        "checks": checks,
    }
    statuses = [c["status"] for c in checks]
    if "FAIL" in statuses:
        result["overall"] = "FAIL"
    elif "NOT_OBSERVED" in statuses:
        result["overall"] = "NOT_OBSERVED"
    else:
        result["overall"] = "PASS"
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="local date YYYY-MM-DD")
    ap.add_argument("--utc-offset-hours", type=int, default=2)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    result = validate(args.date, args.utc_offset_hours)
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
