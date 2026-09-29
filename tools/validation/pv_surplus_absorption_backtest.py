#!/usr/bin/env python3
"""Read-only historical backtest for absorbing otherwise exported PV.

The tool belongs to the retrospective learning/validation plane. It reads the
canonical Pi history database and never writes devices, Homey state, planner
state, or control output.

It quantifies:
- baseline P1 export/import from canonical household-energy intervals;
- additional EV export absorption by rescheduling energy within observed
  connected sessions (without inventing extra driving energy);
- technical warm-water absorption using the validated weekday demand model and
  a zero-intentional-grid-import boiler policy;
- 5/10 kWh battery scenarios (or custom capacities) on the residual stack.

Heating preheat is deliberately not converted to kWh while Thermal Learning
episodes remain UNASSESSED; that boundary is surfaced explicitly in output.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_DB = Path("/home/jeroen/ems/data/ems-history.sqlite")
DEFAULT_PLANNER_DB = Path("/home/jeroen/ems/data/planner-history.sqlite")
DEFAULT_OUTPUT = Path("/home/jeroen/ems/data/pv-surplus-absorption-backtest.json")
TZ = ZoneInfo("Europe/Amsterdam")
SLOT_MINUTES = 15
SLOT_HOURS = SLOT_MINUTES / 60.0

EV_MAX_W_DEFAULT = 11000.0
WW_POWER_W = 1900.0
WW_SLOT_KWH = WW_POWER_W / 1000.0 * SLOT_HOURS
WW_MIN_RUN_SLOTS = 2

WW_EXPECTED_DAILY_KWH = 6.0
WW_EXPECTED_DAILY_KWH_BY_WEEKDAY = {
    0: 5.8,
    1: 4.5,
    2: 6.3,
    3: 7.0,
    4: 5.9,
    5: 7.7,
    6: 7.7,
}


@dataclass
class Slot:
    start: datetime
    import_kwh: float
    export_kwh: float
    quality: str = "observed"
    ev_kwh: float = 0.0

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=SLOT_MINUTES)

    def copy(self) -> "Slot":
        return Slot(
            self.start,
            self.import_kwh,
            self.export_kwh,
            self.quality,
            self.ev_kwh,
        )


def _parse(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"timestamp must be offset-aware: {value}")
    return dt.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _floor_15m(dt: datetime) -> datetime:
    dt = dt.astimezone(timezone.utc)
    minute = (dt.minute // SLOT_MINUTES) * SLOT_MINUTES
    return dt.replace(minute=minute, second=0, microsecond=0)


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return (
        con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        is not None
    )


def _clip_interval(
    start: datetime,
    end: datetime,
    low: datetime | None,
    high: datetime | None,
):
    if low and end <= low:
        return None
    if high and start >= high:
        return None
    return max(start, low) if low else start, min(end, high) if high else end


def load_grid_slots(
    con: sqlite3.Connection,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    max_source_interval_seconds: int = 900,
) -> tuple[list[Slot], dict]:
    """Prefer gross counter-derived household intervals, resampled to 15 min."""
    slots: dict[datetime, list[float]] = defaultdict(lambda: [0.0, 0.0])
    metadata = {
        "source": None,
        "sourceRows": 0,
        "excludedRows": 0,
        "maxSourceIntervalSeconds": max_source_interval_seconds,
    }

    if _table_exists(con, "house_energy_intervals"):
        rows = con.execute(
            """
            SELECT start_ts_utc, end_ts_utc, duration_seconds,
                   import_kwh, export_kwh, quality
            FROM house_energy_intervals
            WHERE import_kwh IS NOT NULL
              AND export_kwh IS NOT NULL
              AND quality!='discontinuity'
            ORDER BY start_ts_utc
            """
        ).fetchall()

        for start_s, end_s, duration_s, imp, exp, quality in rows:
            duration_s = int(duration_s or 0)
            if duration_s <= 0 or duration_s > max_source_interval_seconds:
                metadata["excludedRows"] += 1
                continue
            a = _parse(start_s)
            b = _parse(end_s)
            clipped = _clip_interval(a, b, start, end)
            if clipped is None:
                continue
            a2, b2 = clipped
            total = (b - a).total_seconds()
            if total <= 0:
                continue

            cursor = a2
            while cursor < b2:
                bucket = _floor_15m(cursor)
                bucket_end = bucket + timedelta(minutes=SLOT_MINUTES)
                seg_end = min(bucket_end, b2)
                seconds = (seg_end - cursor).total_seconds()
                fraction = seconds / total
                slots[bucket][0] += max(0.0, float(imp)) * fraction
                slots[bucket][1] += max(0.0, float(exp)) * fraction
                cursor = seg_end

            metadata["sourceRows"] += 1

        if slots:
            metadata["source"] = "HOUSE_ENERGY_INTERVALS_GROSS_COUNTERS"

    if not slots:
        if not _table_exists(con, "measurements_15m"):
            raise RuntimeError("no usable grid history source found")

        clauses = [
            "d.device_key='grid_p1'",
            "m.metric_key='electrical_power_w'",
            "x.energy_wh IS NOT NULL",
        ]
        args: list[str] = []
        if start:
            clauses.append("x.slot_start_utc>=?")
            args.append(_iso(_floor_15m(start)))
        if end:
            clauses.append("x.slot_start_utc<?")
            args.append(_iso(end))

        rows = con.execute(
            f"""
            SELECT x.slot_start_utc, x.energy_wh, x.quality
            FROM measurements_15m x
            JOIN devices d ON d.id=x.device_id
            JOIN metrics m ON m.id=x.metric_id
            WHERE {' AND '.join(clauses)}
            ORDER BY x.slot_start_utc
            """,
            args,
        ).fetchall()
        for ts, energy_wh, quality in rows:
            value = float(energy_wh) / 1000.0
            slots[_parse(ts)] = [max(0.0, value), max(0.0, -value)]
        metadata.update(
            {
                "source": "MEASUREMENTS_15M_SIGNED_P1_FALLBACK",
                "sourceRows": len(rows),
                "excludedRows": 0,
                "warning": (
                    "signed P1 fallback can understate gross import/export when "
                    "both directions occur inside one quarter-hour"
                ),
            }
        )

    result = [
        Slot(ts, imp, exp)
        for ts, (imp, exp) in sorted(slots.items())
    ]
    if not result:
        raise RuntimeError("grid history exists but no slots remain after filters")
    return result, metadata


def load_device_15m_energy(
    con: sqlite3.Connection,
    device_key: str,
    *,
    start: datetime,
    end: datetime,
) -> dict[datetime, float]:
    if not _table_exists(con, "measurements_15m"):
        return {}
    rows = con.execute(
        """
        SELECT x.slot_start_utc, x.energy_wh
        FROM measurements_15m x
        JOIN devices d ON d.id=x.device_id
        JOIN metrics m ON m.id=x.metric_id
        WHERE d.device_key=?
          AND m.metric_key='electrical_power_w'
          AND x.energy_wh IS NOT NULL
          AND x.slot_start_utc>=?
          AND x.slot_start_utc<?
        ORDER BY x.slot_start_utc
        """,
        (device_key, _iso(start), _iso(end)),
    ).fetchall()
    return {
        _parse(ts): max(0.0, float(wh) / 1000.0)
        for ts, wh in rows
    }


def load_connection_events(
    con: sqlite3.Connection,
    *,
    start: datetime,
    end: datetime,
) -> list[tuple[datetime, bool, str]]:
    if not _table_exists(con, "tesla_connection_events"):
        return []

    prior = con.execute(
        """
        SELECT ts_utc, connected, event
        FROM tesla_connection_events
        WHERE ts_utc<=?
        ORDER BY ts_utc DESC
        LIMIT 1
        """,
        (_iso(start),),
    ).fetchall()
    rows = con.execute(
        """
        SELECT ts_utc, connected, event
        FROM tesla_connection_events
        WHERE ts_utc>?
          AND ts_utc<?
        ORDER BY ts_utc
        """,
        (_iso(start), _iso(end)),
    ).fetchall()
    combined = prior + rows
    return [
        (_parse(ts), bool(connected), str(event))
        for ts, connected, event in combined
    ]


def load_planner_connection_states(
    planner_db: Path,
    slots: list[Slot],
) -> tuple[dict[datetime, bool | None], dict]:
    """Reconstruct per-slot Tesla availability from archived planner decisions.

    A planner snapshot is usable only where its own generated/valid interval
    overlaps the replay slot. Missing planner coverage remains UNKNOWN and is
    never carried forward indefinitely.
    """
    result = {slot.start: None for slot in slots}
    meta = {
        "source": "PLANNER_HISTORY_SNAPSHOTS",
        "status": "UNAVAILABLE",
        "snapshotRows": 0,
        "knownSlots": 0,
        "connectedSlots": 0,
        "unknownSlots": len(slots),
        "coveragePct": 0.0,
    }

    if not slots or not planner_db.exists():
        return result, meta

    con = sqlite3.connect(str(planner_db))
    try:
        exists = con.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='planner_snapshots'"
        ).fetchone()
        if not exists:
            return result, meta

        rows = con.execute(
            """
            SELECT generated_at_utc, valid_until_utc, tesla_connected
            FROM planner_snapshots
            WHERE generated_at_utc < ?
            ORDER BY generated_at_utc
            """,
            (_iso(slots[-1].end),),
        ).fetchall()
    finally:
        con.close()

    parsed = []
    for generated_s, valid_s, connected in rows:
        if not generated_s or not valid_s:
            continue
        try:
            generated = _parse(generated_s)
            valid_until = _parse(valid_s)
        except Exception:
            continue
        if valid_until <= generated:
            continue
        if valid_until <= slots[0].start:
            continue
        parsed.append(
            (generated, valid_until, bool(connected))
        )

    meta["snapshotRows"] = len(parsed)
    if not parsed:
        return result, meta

    for slot in slots:
        candidates = [
            row for row in parsed
            if row[0] < slot.end and row[1] > slot.start
        ]
        if not candidates:
            continue
        generated, _valid_until, connected = max(
            candidates,
            key=lambda row: row[0],
        )
        result[slot.start] = connected

    known = sum(value is not None for value in result.values())
    connected = sum(value is True for value in result.values())
    meta.update(
        {
            "status": "OK" if known else "NO_REPLAY_COVERAGE",
            "knownSlots": known,
            "connectedSlots": connected,
            "unknownSlots": len(slots) - known,
            "coveragePct": round(
                100.0 * known / len(slots),
                2,
            ),
        }
    )
    return result, meta


def annotate_ev(slots: list[Slot], ev_energy: dict[datetime, float]) -> None:
    for slot in slots:
        slot.ev_kwh = ev_energy.get(slot.start, 0.0)


def session_ids_from_slot_states(
    slots: list[Slot],
    states: dict[datetime, bool | None],
) -> dict[datetime, int | None]:
    next_session = 0
    active_session: int | None = None
    previous_connected = False
    result: dict[datetime, int | None] = {}

    for slot in slots:
        connected = states.get(slot.start)
        if connected is True:
            if not previous_connected:
                next_session += 1
                active_session = next_session
            result[slot.start] = active_session
            previous_connected = True
        else:
            # UNKNOWN deliberately breaks continuity. Replay may not invent
            # availability through an uncovered planner-history gap.
            result[slot.start] = None
            active_session = None
            previous_connected = False

    return result


def connected_session_ids(
    slots: list[Slot],
    events: list[tuple[datetime, bool, str]],
) -> dict[datetime, int | None]:
    if not events:
        return {slot.start: None for slot in slots}

    events = sorted(events)
    state = False
    session_id: int | None = None
    next_session = 0
    idx = 0
    result: dict[datetime, int | None] = {}

    for slot in slots:
        while idx < len(events) and events[idx][0] <= slot.start:
            _, connected, _ = events[idx]
            if connected and not state:
                next_session += 1
                session_id = next_session
            elif not connected:
                session_id = None
            state = connected
            idx += 1
        result[slot.start] = session_id if state else None

    return result


def allocate_ev_incremental(
    slots: list[Slot],
    session_ids: dict[datetime, int | None],
    *,
    ev_max_w: float,
) -> dict:
    by_session: dict[int, list[Slot]] = defaultdict(list)
    for slot in slots:
        sid = session_ids.get(slot.start)
        if sid is not None:
            by_session[sid].append(slot)

    total_actual = 0.0
    total_shiftable = 0.0
    total_absorb = 0.0
    session_results = []

    for sid, session_slots in sorted(by_session.items()):
        actual = sum(s.ev_kwh for s in session_slots)
        total_actual += actual

        already_export_avoiding = sum(
            s.ev_kwh for s in session_slots if s.export_kwh > 1e-9
        )
        shiftable = max(0.0, actual - already_export_avoiding)
        total_shiftable += shiftable

        remaining = shiftable
        absorbed = 0.0

        candidates = sorted(
            session_slots,
            key=lambda s: (s.export_kwh, -s.start.timestamp()),
            reverse=True,
        )
        for slot in candidates:
            if remaining <= 1e-9 or slot.export_kwh <= 1e-9:
                continue
            actual_w = slot.ev_kwh / SLOT_HOURS * 1000.0
            headroom_kwh = (
                max(0.0, ev_max_w - actual_w) / 1000.0 * SLOT_HOURS
            )
            take = min(slot.export_kwh, headroom_kwh, remaining)
            if take <= 0:
                continue
            slot.export_kwh -= take
            absorbed += take
            remaining -= take

        total_absorb += absorbed
        session_results.append(
            {
                "session": sid,
                "actualEnergyKWh": round(actual, 4),
                "alreadyAvoidedExportKWh": round(
                    already_export_avoiding, 4
                ),
                "shiftableFromNonExportKWh": round(shiftable, 4),
                "additionalAbsorbedExportKWh": round(absorbed, 4),
                "unplacedShiftableKWh": round(max(0.0, remaining), 4),
            }
        )

    return {
        "status": "OK" if by_session else "INSUFFICIENT_CONNECTION_HISTORY",
        "sessionCount": len(by_session),
        "evMaxW": round(ev_max_w),
        "actualEnergyKWh": round(total_actual, 4),
        "shiftableFromNonExportKWh": round(total_shiftable, 4),
        "additionalAbsorbableExportKWh": round(total_absorb, 4),
        "sessions": session_results,
        "method": "RESCHEDULE_WITHIN_OBSERVED_CONNECTED_SESSION",
        "classification": "TECHNICAL_SESSION_UPPER_BOUND",
        "deadlineConstraintApplied": False,
        "note": (
            "Energy is never invented and may only move inside an observed "
            "connected session. Historical user deadlines earlier than session "
            "disconnect are not reconstructed in V0.1, so this is an upper "
            "bound on additional technical PV absorption."
        ),
    }


def _local_day(slot: Slot) -> str:
    return slot.start.astimezone(TZ).date().isoformat()


def _ww_expected_kwh(day_s: str) -> float:
    day = datetime.fromisoformat(day_s).date()
    return WW_EXPECTED_DAILY_KWH_BY_WEEKDAY.get(
        day.weekday(),
        WW_EXPECTED_DAILY_KWH,
    )


def allocate_ww_zero_import(slots: list[Slot]) -> dict:
    by_day: dict[str, list[Slot]] = defaultdict(list)
    for slot in slots:
        local = slot.start.astimezone(TZ)
        hm = (local.hour, local.minute)
        if (9, 30) <= hm < (19, 0):
            by_day[_local_day(slot)].append(slot)

    absorbed_total = 0.0
    planned_total = 0.0
    daily = []

    for day_s, day_slots in sorted(by_day.items()):
        need = _ww_expected_kwh(day_s)
        required_slots = math.ceil(need / WW_SLOT_KWH - 1e-12)

        eligible = [
            s for s in day_slots
            if s.export_kwh + 1e-9 >= WW_SLOT_KWH
        ]
        eligible.sort(key=lambda s: s.start)

        windows: list[list[Slot]] = []
        current: list[Slot] = []
        for slot in eligible:
            if (
                current
                and slot.start - current[-1].start
                != timedelta(minutes=SLOT_MINUTES)
            ):
                if len(current) >= WW_MIN_RUN_SLOTS:
                    windows.append(current)
                current = []
            current.append(slot)
        if len(current) >= WW_MIN_RUN_SLOTS:
            windows.append(current)

        windows.sort(
            key=lambda w: (
                -sum(s.export_kwh for s in w) / len(w),
                w[0].start,
            )
        )

        selected: list[Slot] = []
        remaining_slots = required_slots
        for window in windows:
            if remaining_slots < WW_MIN_RUN_SLOTS:
                break
            take_n = min(len(window), remaining_slots)
            if take_n < WW_MIN_RUN_SLOTS:
                continue
            selected.extend(window[:take_n])
            remaining_slots -= take_n

        absorbed = 0.0
        remaining_need_kwh = need

        for slot in selected:
            if remaining_need_kwh <= 1e-9:
                break

            # Preserve the contiguous technical run while never allocating
            # more WW energy than the modeled daily demand.
            take = min(
                WW_SLOT_KWH,
                slot.export_kwh,
                remaining_need_kwh,
            )
            slot.export_kwh -= take
            absorbed += take
            remaining_need_kwh -= take

        planned = absorbed
        absorbed_total += absorbed
        planned_total += planned

        daily.append(
            {
                "date": day_s,
                "modeledDemandKWh": round(need, 3),
                "selectedRunKWh": round(planned, 3),
                "absorbedExportKWh": round(absorbed, 3),
                "unservedByZeroImportPolicyKWh": round(
                    max(0.0, need - planned), 3
                ),
            }
        )

    return {
        "status": "TECHNICAL_ONLY",
        "boilerPowerW": int(WW_POWER_W),
        "windowLocal": "09:30-19:00",
        "minRunMinutes": WW_MIN_RUN_SLOTS * SLOT_MINUTES,
        "intentionalGridImportAllowed": False,
        "modeledDemandKWh": round(
            sum(_ww_expected_kwh(d) for d in by_day), 4
        ),
        "selectedRunKWh": round(planned_total, 4),
        "absorbableExportKWh": round(absorbed_total, 4),
        "economicAuthority": "WW_SEASONAL_SOURCE_ADVISOR",
        "economicNote": (
            "This backtest quantifies technical PV absorption only. "
            "BOILER/CV source economics remain owned by the Seasonal Advisor."
        ),
        "daily": daily,
    }


def simulate_battery(
    slots: list[Slot],
    *,
    capacity_kwh: float,
    max_power_w: float,
    charge_efficiency: float,
    discharge_efficiency: float,
) -> dict:
    soc = 0.0
    pv_charged = 0.0
    import_avoided = 0.0
    losses = 0.0
    power_kwh = max_power_w / 1000.0 * SLOT_HOURS

    for slot in slots:
        net_import = max(0.0, slot.import_kwh - slot.export_kwh)
        net_export = max(0.0, slot.export_kwh - slot.import_kwh)

        if net_import > 0 and soc > 1e-9:
            deliverable = min(
                net_import,
                power_kwh,
                soc * discharge_efficiency,
            )
            if deliverable > 0:
                battery_draw = deliverable / discharge_efficiency
                soc -= battery_draw
                import_avoided += deliverable
                losses += battery_draw - deliverable
                slot.import_kwh = max(
                    0.0, slot.import_kwh - deliverable
                )

        elif net_export > 0 and soc < capacity_kwh - 1e-9:
            input_limit = (
                capacity_kwh - soc
            ) / charge_efficiency
            charge_input = min(
                net_export,
                power_kwh,
                input_limit,
            )
            if charge_input > 0:
                stored = charge_input * charge_efficiency
                soc += stored
                pv_charged += charge_input
                losses += charge_input - stored
                slot.export_kwh = max(
                    0.0, slot.export_kwh - charge_input
                )

    return {
        "capacityKWh": round(capacity_kwh, 3),
        "maxPowerW": round(max_power_w),
        "chargeEfficiency": charge_efficiency,
        "dischargeEfficiency": discharge_efficiency,
        "pvChargedFromOtherwiseExportKWh": round(pv_charged, 4),
        "gridImportAvoidedKWh": round(import_avoided, 4),
        "conversionLossKWh": round(losses, 4),
        "endingSocKWh": round(soc, 4),
    }


def _sum(slots: list[Slot], attr: str) -> float:
    return sum(float(getattr(s, attr)) for s in slots)


def overlap_summary(
    *,
    ev_standalone_kwh: float,
    ww_standalone_kwh: float,
    ev_then_ww_kwh: float,
    ww_then_ev_kwh: float,
) -> dict:
    best_combined = max(ev_then_ww_kwh, ww_then_ev_kwh)
    standalone_sum = ev_standalone_kwh + ww_standalone_kwh
    return {
        "standaloneSumKWh": round(standalone_sum, 4),
        "bestCombinedTwoOrderingsKWh": round(best_combined, 4),
        "overlapAgainstBestTwoOrderingsKWh": round(
            max(0.0, standalone_sum - best_combined),
            4,
        ),
        "orderSensitivityKWh": round(
            abs(ev_then_ww_kwh - ww_then_ev_kwh),
            4,
        ),
    }


def run_backtest(
    con: sqlite3.Connection,
    *,
    planner_db: Path = DEFAULT_PLANNER_DB,
    start: datetime | None = None,
    end: datetime | None = None,
    ev_max_w: float = EV_MAX_W_DEFAULT,
    battery_capacities: tuple[float, ...] = (5.0, 10.0),
    battery_power_w: float = 5000.0,
    charge_efficiency: float = 0.95,
    discharge_efficiency: float = 0.95,
) -> dict:
    slots, grid_meta = load_grid_slots(
        con,
        start=start,
        end=end,
    )
    period_start = slots[0].start
    period_end = slots[-1].end

    ev_energy = load_device_15m_energy(
        con,
        "tesla",
        start=period_start,
        end=period_end,
    )
    annotate_ev(slots, ev_energy)

    planner_states, connection_meta = load_planner_connection_states(
        planner_db,
        slots,
    )
    if connection_meta["knownSlots"] > 0:
        session_ids = session_ids_from_slot_states(
            slots,
            planner_states,
        )
    else:
        events = load_connection_events(
            con,
            start=period_start,
            end=period_end,
        )
        session_ids = connected_session_ids(slots, events)
        connection_meta = {
            "source": "TESLA_CONNECTION_EVENTS_FALLBACK",
            "status": "OK" if events else "UNAVAILABLE",
            "eventRows": len(events),
            "knownSlots": sum(
                session_ids.get(slot.start) is not None
                for slot in slots
            ),
            "connectedSlots": sum(
                session_ids.get(slot.start) is not None
                for slot in slots
            ),
            "unknownSlots": 0 if events else len(slots),
            "coveragePct": 100.0 if events else 0.0,
            "warning": (
                "legacy event history is used only because planner-history "
                "has no usable replay coverage"
            ),
        }

    baseline_export = _sum(slots, "export_kwh")
    baseline_import = _sum(slots, "import_kwh")

    # EV-first is also the standalone EV scenario because it sees the raw
    # baseline export before any other flexible consumer claims the same slots.
    after_ev = [s.copy() for s in slots]
    ev = allocate_ev_incremental(
        after_ev,
        session_ids,
        ev_max_w=ev_max_w,
    )
    ev["connectionHistory"] = connection_meta
    residual_after_ev = _sum(after_ev, "export_kwh")

    # WW standalone sees the same raw baseline. This is required to distinguish
    # gross technical potential from marginal contribution in one chosen stack.
    ww_only_slots = [s.copy() for s in slots]
    ww_standalone = allocate_ww_zero_import(ww_only_slots)
    residual_after_ww_only = _sum(ww_only_slots, "export_kwh")

    # Primary comparison order: EV -> WW.
    after_ww = [s.copy() for s in after_ev]
    ww = allocate_ww_zero_import(after_ww)
    residual_before_battery = _sum(after_ww, "export_kwh")

    # Alternative order: WW -> EV. The difference is evidence that both
    # resources compete for the same sunny slots and a fixed priority would
    # bias the apparent value of the first resource.
    ww_then_ev_slots = [s.copy() for s in slots]
    ww_first = allocate_ww_zero_import(ww_then_ev_slots)
    ev_after_ww = allocate_ev_incremental(
        ww_then_ev_slots,
        session_ids,
        ev_max_w=ev_max_w,
    )
    residual_ww_then_ev = _sum(
        ww_then_ev_slots,
        "export_kwh",
    )

    ev_then_ww_absorbed = (
        baseline_export - residual_before_battery
    )
    ww_then_ev_absorbed = (
        baseline_export - residual_ww_then_ev
    )
    overlap = overlap_summary(
        ev_standalone_kwh=ev["additionalAbsorbableExportKWh"],
        ww_standalone_kwh=ww_standalone["absorbableExportKWh"],
        ev_then_ww_kwh=ev_then_ww_absorbed,
        ww_then_ev_kwh=ww_then_ev_absorbed,
    )

    # Battery standalone shows what storage could do if no additional flex
    # development existed. The residual scenarios below show its marginal value
    # after EV + WW have already consumed export.
    battery_standalone = []
    for capacity in battery_capacities:
        scenario_slots = [s.copy() for s in slots]
        battery = simulate_battery(
            scenario_slots,
            capacity_kwh=capacity,
            max_power_w=battery_power_w,
            charge_efficiency=charge_efficiency,
            discharge_efficiency=discharge_efficiency,
        )
        residual_export = _sum(scenario_slots, "export_kwh")
        battery["residualExportKWh"] = round(
            residual_export, 4
        )
        battery["residualImportKWh"] = round(
            _sum(scenario_slots, "import_kwh"), 4
        )
        battery["totalExportAbsorbedVsBaselineKWh"] = round(
            baseline_export - residual_export, 4
        )
        battery_standalone.append(battery)

    batteries = []
    for capacity in battery_capacities:
        scenario_slots = [s.copy() for s in after_ww]
        battery = simulate_battery(
            scenario_slots,
            capacity_kwh=capacity,
            max_power_w=battery_power_w,
            charge_efficiency=charge_efficiency,
            discharge_efficiency=discharge_efficiency,
        )
        residual_export = _sum(scenario_slots, "export_kwh")
        battery["residualExportKWh"] = round(
            residual_export, 4
        )
        battery["residualImportKWh"] = round(
            _sum(scenario_slots, "import_kwh"), 4
        )
        battery["totalExportAbsorbedVsBaselineKWh"] = round(
            baseline_export - residual_export, 4
        )
        batteries.append(battery)

    observed_days = sorted({_local_day(s) for s in slots})

    return {
        "schema": "EMS_PV_SURPLUS_ABSORPTION_BACKTEST_V0.1",
        "mode": "READ_ONLY",
        "controlWrites": False,
        "generatedAt": _iso(datetime.now(timezone.utc)),
        "period": {
            "start": _iso(period_start),
            "end": _iso(period_end),
            "slotMinutes": SLOT_MINUTES,
            "slots": len(slots),
            "localDays": len(observed_days),
        },
        "source": grid_meta,
        "baseline": {
            "gridExportKWh": round(baseline_export, 4),
            "gridImportKWh": round(baseline_import, 4),
        },
        "allocationStack": {
            "order": [
                "HOUSE_BASELOAD_ALREADY_IN_P1",
                "EV_SESSION_SHIFT",
                "WW_ZERO_IMPORT_TECHNICAL",
                "HEATING_PREHEAT_NOT_COUNTED_UNTIL_ASSESSED",
                "FLEX_APPLIANCES_NOT_COUNTED_DATA_MODEL_INCOMPLETE",
                "BATTERY",
                "EXPORT",
            ],
            "ev": ev,
            "residualExportAfterEvKWh": round(
                residual_after_ev, 4
            ),
            "warmWater": ww,
            "residualExportBeforeBatteryKWh": round(
                residual_before_battery, 4
            ),
            "heatingPreheat": {
                "status": "UNASSESSED_NOT_COUNTED",
                "reason": (
                    "Thermal Learning episodes are currently raw evidence; "
                    "no validated kWh storage/avoidance parameter exists."
                ),
            },
            "householdAppliances": {
                "status": "NOT_COUNTED_DATA_MODEL_INCOMPLETE",
                "reason": (
                    "Canonical Pi history currently archives washer/dryer active "
                    "state but does not yet provide a validated per-cycle energy "
                    "demand + user deadline model suitable for counterfactual "
                    "rescheduling. Dishwasher is likewise not a canonical flex "
                    "history input for this replay."
                ),
            },
            "batteryScenarios": batteries,
        },
        "comparativeAnalysis": {
            "standalone": {
                "evAdditionalAbsorbableExportKWh": round(
                    ev["additionalAbsorbableExportKWh"], 4
                ),
                "wwAbsorbableExportKWh": round(
                    ww_standalone["absorbableExportKWh"], 4
                ),
                "wwResidualExportKWh": round(
                    residual_after_ww_only, 4
                ),
                "batteryScenarios": battery_standalone,
            },
            "orderedFlex": [
                {
                    "order": ["EV", "WW"],
                    "evMarginalKWh": round(
                        ev["additionalAbsorbableExportKWh"], 4
                    ),
                    "wwMarginalKWh": round(
                        ww["absorbableExportKWh"], 4
                    ),
                    "combinedAbsorbedExportKWh": round(
                        ev_then_ww_absorbed, 4
                    ),
                    "residualExportKWh": round(
                        residual_before_battery, 4
                    ),
                },
                {
                    "order": ["WW", "EV"],
                    "wwMarginalKWh": round(
                        ww_first["absorbableExportKWh"], 4
                    ),
                    "evMarginalKWh": round(
                        ev_after_ww["additionalAbsorbableExportKWh"], 4
                    ),
                    "combinedAbsorbedExportKWh": round(
                        ww_then_ev_absorbed, 4
                    ),
                    "residualExportKWh": round(
                        residual_ww_then_ev, 4
                    ),
                },
            ],
            "overlap": overlap,
        },
        "interpretation": {
            "technicalVsEconomicSeparated": True,
            "evNoExtraDrivingEnergyInvented": True,
            "evHistoricalDeadlineConstraintApplied": False,
            "evResultIsSessionUpperBound": True,
            "wwSourceEconomicsDelegated": True,
            "heatingNoInventedThermalCapacity": True,
            "batteryInitialSocKWh": 0.0,
        },
    }


def print_summary(result: dict) -> None:
    p = result["period"]
    b = result["baseline"]
    stack = result["allocationStack"]
    ev = stack["ev"]
    ww = stack["warmWater"]

    print("PV surplus absorption backtest — READ ONLY")
    print(f"period              : {p['start']} -> {p['end']}")
    print(
        f"slots / local days  : "
        f"{p['slots']} / {p['localDays']}"
    )
    print(
        f"grid source         : "
        f"{result['source']['source']}"
    )
    print(
        f"baseline export     : "
        f"{b['gridExportKWh']:.3f} kWh"
    )
    print(
        f"baseline import     : "
        f"{b['gridImportKWh']:.3f} kWh"
    )
    print()
    print(
        f"EV extra absorbable : "
        f"{ev['additionalAbsorbableExportKWh']:.3f} kWh "
        f"({ev['status']}, {ev['sessionCount']} sessions)"
    )
    print(
        f"WW technical        : "
        f"{ww['absorbableExportKWh']:.3f} kWh "
        "(zero intentional grid import)"
    )
    print(
        "Heating preheat     : "
        "not counted — Thermal Learning UNASSESSED"
    )
    print(
        f"Residual pre-battery: "
        f"{stack['residualExportBeforeBatteryKWh']:.3f} kWh"
    )
    print()

    for battery in stack["batteryScenarios"]:
        print(
            f"Battery {battery['capacityKWh']:.1f} kWh     : "
            f"PV charge "
            f"{battery['pvChargedFromOtherwiseExportKWh']:.3f} kWh, "
            f"import avoided "
            f"{battery['gridImportAvoidedKWh']:.3f} kWh, "
            f"residual export "
            f"{battery['residualExportKWh']:.3f} kWh"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
    )
    parser.add_argument(
        "--planner-db",
        type=Path,
        default=DEFAULT_PLANNER_DB,
        help="planner decision history used for EV connected-state replay",
    )
    parser.add_argument(
        "--start",
        help="offset-aware ISO timestamp",
    )
    parser.add_argument(
        "--end",
        help="offset-aware ISO timestamp",
    )
    parser.add_argument(
        "--ev-max-w",
        type=float,
        default=EV_MAX_W_DEFAULT,
    )
    parser.add_argument(
        "--battery-kwh",
        type=float,
        action="append",
        dest="battery_kwh",
        help="battery usable capacity; repeat for multiple scenarios",
    )
    parser.add_argument(
        "--battery-power-w",
        type=float,
        default=5000.0,
    )
    parser.add_argument(
        "--charge-efficiency",
        type=float,
        default=0.95,
    )
    parser.add_argument(
        "--discharge-efficiency",
        type=float,
        default=0.95,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument(
        "--no-write-output",
        action="store_true",
        help="do not write the derived JSON artifact",
    )
    args = parser.parse_args()

    start = _parse(args.start) if args.start else None
    end = _parse(args.end) if args.end else None
    if start and end and end <= start:
        parser.error("--end must be later than --start")

    capacities = tuple(args.battery_kwh or (5.0, 10.0))
    if any(v <= 0 for v in capacities):
        parser.error("battery capacities must be > 0")
    if args.ev_max_w <= 0 or args.battery_power_w <= 0:
        parser.error("power limits must be > 0")

    for name, value in (
        ("charge efficiency", args.charge_efficiency),
        ("discharge efficiency", args.discharge_efficiency),
    ):
        if not (0 < value <= 1):
            parser.error(f"{name} must be in (0, 1]")

    con = sqlite3.connect(str(args.db))
    try:
        result = run_backtest(
            con,
            planner_db=args.planner_db,
            start=start,
            end=end,
            ev_max_w=args.ev_max_w,
            battery_capacities=capacities,
            battery_power_w=args.battery_power_w,
            charge_efficiency=args.charge_efficiency,
            discharge_efficiency=args.discharge_efficiency,
        )
    finally:
        con.close()

    if not args.no_write_output:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        tmp = args.output.with_suffix(
            args.output.suffix + ".tmp"
        )
        tmp.write_text(
            json.dumps(result, indent=2) + "\n"
        )
        tmp.replace(args.output)

    print_summary(result)
    if not args.no_write_output:
        print()
        print(f"output              : {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
