#!/usr/bin/env python3
import argparse
import json
from datetime import datetime
from pathlib import Path

BOILER_W = 1900
STEP_H = 0.25


def ts(v):
    return datetime.fromisoformat(str(v).replace('Z', '+00:00')).timestamp()


def price(slot):
    v = slot.get('price_eur_kwh')
    return float(v) if isinstance(v, (int, float)) else 999.0


def surplus(slot):
    return max(0.0, float(slot.get('pvSurplusBeforeFlexW') or 0.0))


def rank_old(slots, contract):
    def key(s):
        capped = min(BOILER_W, surplus(s))
        p = price(s) if contract == 'DYNAMIC' else 0.0
        return (-capped, p, ts(s['start']))
    return sorted(slots, key=key)


def rank_new(slots, contract):
    def key(s):
        raw = surplus(s)
        full = raw >= BOILER_W
        p = price(s) if contract == 'DYNAMIC' else 0.0
        return (0 if full else 1, -raw, p, ts(s['start']))
    return sorted(slots, key=key)


def allocate(ranked, need_kwh):
    remain = float(need_kwh)
    chosen = []
    for s in ranked:
        if remain <= 1e-9:
            break
        e = min(BOILER_W / 1000 * STEP_H, remain)
        pv_w = min(BOILER_W, surplus(s))
        grid_w = max(0.0, BOILER_W - pv_w)
        chosen.append({
            **s,
            'allocatedKWh': round(e, 3),
            'pvCoverageW': round(pv_w),
            'gridRequiredW': round(grid_w),
        })
        remain -= e
    return chosen, max(0.0, remain)


def metrics(chosen):
    pv_kwh = sum(float(s['pvCoverageW']) / 1000 * STEP_H for s in chosen)
    grid_kwh = sum(float(s['gridRequiredW']) / 1000 * STEP_H for s in chosen)
    cost = sum((float(s['gridRequiredW']) / 1000 * STEP_H) * (price(s) if price(s) < 900 else 0) for s in chosen)
    return {
        'slots': len(chosen),
        'pvCoveredKWh': round(pv_kwh, 4),
        'gridRequiredKWh': round(grid_kwh, 4),
        'gridEnergyCostEur': round(cost, 4),
        'firstStart': chosen[0]['start'] if chosen else None,
        'lastStart': chosen[-1]['start'] if chosen else None,
        'meanTrueSurplusW': round(sum(surplus(s) for s in chosen) / len(chosen), 1) if chosen else None,
        'minTrueSurplusW': round(min((surplus(s) for s in chosen), default=0), 1),
        'maxTrueSurplusW': round(max((surplus(s) for s in chosen), default=0), 1),
    }


def find_future_plan(payload):
    p = payload.get('plan', payload)
    inputs = p.get('inputs', {})
    plan = p.get('plan', {})
    actions = plan.get('actions', [])
    ww = plan.get('warmWater', {})
    future = ww.get('futureDays') or []
    target = next((d for d in future if float(d.get('derivedEnergyKWh') or 0) > 0), None)
    if target is None:
        raise SystemExit('No future-day WW requirement found in snapshot')
    deadline = ts(target['deadlineAt'])
    date = target['date']
    candidates = [s for s in actions if s.get('localDate') == date and ts(s['start']) < deadline]
    return str(inputs.get('contract', 'UNKNOWN')).upper(), float(target['derivedEnergyKWh']), date, target['deadlineAt'], candidates


def compare(payload):
    contract, need_kwh, date, deadline_at, candidates = find_future_plan(payload)
    old, old_un = allocate(rank_old(candidates, contract), need_kwh)
    new, new_un = allocate(rank_new(candidates, contract), need_kwh)
    old_m, new_m = metrics(old), metrics(new)
    old_idx = {s['i'] for s in old}
    new_idx = {s['i'] for s in new}
    return {
        'schema': 'EM2_WW_RANKING_AB_V0.1',
        'contract': contract,
        'planningDate': date,
        'deadlineAt': deadline_at,
        'requiredKWh': need_kwh,
        'candidateSlots': len(candidates),
        'old': {**old_m, 'unallocatedKWh': round(old_un, 4), 'slotIndices': sorted(old_idx)},
        'candidate': {**new_m, 'unallocatedKWh': round(new_un, 4), 'slotIndices': sorted(new_idx)},
        'delta': {
            'pvCoveredKWh': round(new_m['pvCoveredKWh'] - old_m['pvCoveredKWh'], 4),
            'gridRequiredKWh': round(new_m['gridRequiredKWh'] - old_m['gridRequiredKWh'], 4),
            'gridEnergyCostEur': round(new_m['gridEnergyCostEur'] - old_m['gridEnergyCostEur'], 4),
            'changedSlots': len(old_idx.symmetric_difference(new_idx)),
            'meanTrueSurplusW': round(new_m['meanTrueSurplusW'] - old_m['meanTrueSurplusW'], 1),
        },
        'pass': (
            len(old) == len(new)
            and old_un <= 1e-9 and new_un <= 1e-9
            and new_m['pvCoveredKWh'] + 1e-9 >= old_m['pvCoveredKWh']
            and new_m['gridRequiredKWh'] <= old_m['gridRequiredKWh'] + 1e-9
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('snapshot', nargs='?', default='docs/data/energy-planner-shadow.json')
    ap.add_argument('--out')
    args = ap.parse_args()
    payload = json.loads(Path(args.snapshot).read_text())
    result = compare(payload)
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + '\n')
    raise SystemExit(0 if result['pass'] else 1)


if __name__ == '__main__':
    main()
