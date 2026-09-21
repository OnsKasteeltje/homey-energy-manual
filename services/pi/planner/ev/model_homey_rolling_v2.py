#!/usr/bin/env python3
"""Pure model of Homey-side EV V2 rolling executor state for shadow validation."""
from dataclasses import dataclass
from datetime import datetime, timezone

MAX_SAMPLES = 5


def _ts(v):
    d=datetime.fromisoformat(str(v).replace("Z","+00:00"))
    if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def available_pv_from_homey(*, p1_measure_power_w, ev_actual_power_w):
    """Homey P1: import positive, export negative."""
    return max(0.0, -float(p1_measure_power_w) + max(0.0,float(ev_actual_power_w)))


def append_sample(samples, *, at, available_pv_w):
    """Keep at most five ordered timestamped one-minute executor samples."""
    now=_ts(at)
    clean=[]
    for s in samples or []:
        try:
            t=_ts(s["at"]); w=max(0.0,float(s["availablePvW"]))
        except (KeyError,TypeError,ValueError):
            continue
        if t < now:
            clean.append({"at":t.isoformat().replace("+00:00","Z"),"availablePvW":w})
    clean.append({"at":now.isoformat().replace("+00:00","Z"),"availablePvW":max(0.0,float(available_pv_w))})
    return clean[-MAX_SAMPLES:]


def rolling_w(samples):
    vals=[float(s["availablePvW"]) for s in (samples or [])]
    return sum(vals)/len(vals) if vals else None
