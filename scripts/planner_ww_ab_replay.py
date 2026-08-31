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


def rank_full(slots):
    return sorted(
        [s for s in slots if surplus(s) >= BOILER_W],
        key=lambda s: (-surplus(s), ts(s['start'])),
    )


def rank_grid_v049(slots, contract, price_usable=True):
    def key(s):
        p = price(s) if contract == 'DYNAMIC' and price_usable else 0.0
        return (p, -surplus(s), ts(s['start']))
    return sorted(slots, key=key)


def rank_grid_candidate(slots, contract, price_usable=True):
    def key(s):
        pv = surplus(s)
        has_pv = pv > 0
        p = price(s) if contract == 'DYNAMIC' and price_usable else 0.0
        if has_pv:
            return (0, -pv, p, ts(s['start']))
        return (1, 0.0, p, ts(s['start']))
    return sorted(slots, key=key)


def allocate(slots, need_kwh, contract, candidate=False, price_usable=True):
    remain = float(need_kwh)
    chosen = []
    used = set()

    def take(s):
        nonlocal remain
        if remain <= 1e-9 or s['start'] in used:
            return
        e = min(BOILER_W / 1000 * STEP_H, remain)
        pv_w = min(BOILER_W, surplus(s))
        grid_w = max(0.0, BOILER_W - pv_w)
        chosen.append({
            **s,
            'allocatedKWh': round(e, 3),
            'pvCoverageW': round(pv_w),
            'gridRequiredW': round(grid_w),
        })
        used.add(s['start'])
        remain -= e

    for s in rank_full(slots):
        take(s)
        if remain <= 1e-9:
            break

    if remain > 1e-9:
        rest = [s for s in slots if s['start'] not in used]
        ranked = (
            rank_grid_candidate(rest, contract, price_usable)
            if candidate
            else rank_grid_v049(rest, contract, price_usable)
        )
        for s in ranked:
            take(s)
            if remain <= 1e-9:
                break

    return sorted(chosen, key=lambda s: ts(s['start'])), max(0.0, remain)


def metrics(chosen):
    pv_kwh = sum(float(s['pvCoverageW']) / 1000 * STEP_H for s in chosen)
    grid_kwh = sum(float(s['gridRequiredW']) / 1000 * STEP_H for s in chosen)
    cost = sum(
        (float(s['gridRequiredW']) / 1000 * STEP_H)
        * (price(s) if price(s) < 900 else 0)
        for s in chosen
    )
    return {
        'slots': len(chosen),
        'pvCoveredKWh': round(pv_kwh, 4),
        'gridRequiredKWh': round(grid_kwh, 4),
        'gridEnergyCostEur': round(cost, 4),
        'meanTrueSurplusW': round(
            sum(surplus(s) for s in chosen) / len(chosen), 1
        ) if chosen else None,
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
    candidates = [
        s for s in actions
        if s.get('localDate') == date and ts(s['start']) < deadline
    ]
    price_info = inputs.get('price') or {}
    return (
        str(inputs.get('contract', 'UNKNOWN')).upper(),
        bool(price_info.get('usable', True)),
        float(target['derivedEnergyKWh']),
        date,
        target['deadlineAt'],
        candidates,
    )


def compare(payload):
    contract, price_usable, need_kwh, date, deadline_at, candidates = find_future_plan(payload)
    old, old_un = allocate(candidates, need_kwh, contract, candidate=False, price_usable=price_usable)
    new, new_un = allocate(candidates, need_kwh, contract, candidate=True, price_usable=price_usable)
    old_m, new_m = metrics(old), metrics(new)
    old_idx = {s['i'] for s in old}
    new_idx = {s['i'] for s in new}
    return {
        'schema': 'EM2_WW_RANKING_AB_V0.2',
        'contract': contract,
        'priceUsable': price_usable,
        'planningDate': date,
        'deadlineAt': deadline_at,
        'requiredKWh': need_kwh,
        'candidateSlots': len(candidates),
        'v0_4_9': {
            **old_m,
            'unallocatedKWh': round(old_un, 4),
            'slotIndices': sorted(old_idx),
        },
        'v0_4_10_candidate': {
            **new_m,
            'unallocatedKWh': round(new_un, 4),
            'slotIndices': sorted(new_idx),
        },
        'delta': {
            'pvCoveredKWh': round(new_m['pvCoveredKWh'] - old_m['pvCoveredKWh'], 4),
            'gridRequiredKWh': round(new_m['gridRequiredKWh'] - old_m['gridRequiredKWh'], 4),
            'gridEnergyCostEur': round(new_m['gridEnergyCostEur'] - old_m['gridEnergyCostEur'], 4),
            'changedSlots': len(old_idx.symmetric_difference(new_idx)),
            'meanTrueSurplusW': round(new_m['meanTrueSurplusW'] - old_m['meanTrueSurplusW'], 1),
        },
        'pass': (
            len(old) == len(new)
            and old_un <= 1e-9
            and new_un <= 1e-9
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
