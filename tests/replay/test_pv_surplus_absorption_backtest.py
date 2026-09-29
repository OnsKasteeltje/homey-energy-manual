#!/usr/bin/env python3

import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "tools/validation/pv_surplus_absorption_backtest.py"
)

spec = importlib.util.spec_from_file_location(
    "pv_surplus_absorption_backtest",
    MODULE_PATH,
)
backtest = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = backtest
spec.loader.exec_module(backtest)


class PvSurplusAbsorptionBacktestTest(unittest.TestCase):
    def test_planner_history_drives_connected_slots_without_carrying_gaps(self):
        start = datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc)
        slots = [
            backtest.Slot(
                start + timedelta(minutes=15 * i),
                import_kwh=0.0,
                export_kwh=0.0,
            )
            for i in range(4)
        ]

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "planner-history.sqlite"
            con = sqlite3.connect(db)
            con.execute("""
                CREATE TABLE planner_snapshots (
                    generated_at_utc TEXT NOT NULL,
                    valid_until_utc TEXT,
                    tesla_connected INTEGER
                )
            """)
            con.executemany(
                "INSERT INTO planner_snapshots VALUES (?, ?, ?)",
                [
                    (
                        "2026-09-20T10:01:00Z",
                        "2026-09-20T10:15:00Z",
                        1,
                    ),
                    (
                        "2026-09-20T10:16:00Z",
                        "2026-09-20T10:30:00Z",
                        1,
                    ),
                    (
                        "2026-09-20T10:46:00Z",
                        "2026-09-20T11:00:00Z",
                        0,
                    ),
                ],
            )
            con.commit()
            con.close()

            states, meta = backtest.load_planner_connection_states(
                db,
                slots,
            )

        self.assertIs(states[slots[0].start], True)
        self.assertIs(states[slots[1].start], True)
        self.assertIsNone(states[slots[2].start])
        self.assertIs(states[slots[3].start], False)
        self.assertEqual(meta["knownSlots"], 3)
        self.assertEqual(meta["unknownSlots"], 1)

        sessions = backtest.session_ids_from_slot_states(
            slots,
            states,
        )
        self.assertEqual(sessions[slots[0].start], 1)
        self.assertEqual(sessions[slots[1].start], 1)
        self.assertIsNone(sessions[slots[2].start])
        self.assertIsNone(sessions[slots[3].start])

    def test_ev_only_shifts_energy_not_already_avoiding_export(self):
        start = datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc)
        slots = [
            backtest.Slot(
                start + timedelta(minutes=15 * i),
                import_kwh=0.0 if i < 2 else 0.5,
                export_kwh=1.0 if i < 2 else 0.0,
                ev_kwh=0.0 if i < 2 else 0.5,
            )
            for i in range(4)
        ]
        sessions = {slot.start: 1 for slot in slots}

        result = backtest.allocate_ev_incremental(
            slots,
            sessions,
            ev_max_w=11000,
        )

        self.assertAlmostEqual(
            result["actualEnergyKWh"],
            1.0,
            places=6,
        )
        self.assertAlmostEqual(
            result["shiftableFromNonExportKWh"],
            1.0,
            places=6,
        )
        self.assertAlmostEqual(
            result["additionalAbsorbableExportKWh"],
            1.0,
            places=6,
        )
        self.assertAlmostEqual(
            sum(slot.export_kwh for slot in slots),
            1.0,
            places=6,
        )

    def test_ev_does_not_double_count_existing_pv_charge(self):
        start = datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc)
        slots = [
            backtest.Slot(
                start,
                import_kwh=0.0,
                export_kwh=0.5,
                ev_kwh=0.5,
            ),
            backtest.Slot(
                start + timedelta(minutes=15),
                import_kwh=0.5,
                export_kwh=0.0,
                ev_kwh=0.5,
            ),
        ]
        sessions = {slot.start: 1 for slot in slots}

        result = backtest.allocate_ev_incremental(
            slots,
            sessions,
            ev_max_w=11000,
        )

        self.assertAlmostEqual(
            result["actualEnergyKWh"],
            1.0,
            places=6,
        )
        self.assertAlmostEqual(
            result["shiftableFromNonExportKWh"],
            0.5,
            places=6,
        )
        self.assertAlmostEqual(
            result["additionalAbsorbableExportKWh"],
            0.5,
            places=6,
        )

    def test_ww_requires_contiguous_full_pv_run(self):
        # 08:00 UTC = 10:00 Europe/Amsterdam on 2026-09-20.
        start = datetime(2026, 9, 20, 8, 0, tzinfo=timezone.utc)
        slots = [
            backtest.Slot(
                start,
                import_kwh=0.0,
                export_kwh=backtest.WW_SLOT_KWH,
            ),
            backtest.Slot(
                start + timedelta(minutes=15),
                import_kwh=0.0,
                export_kwh=backtest.WW_SLOT_KWH,
            ),
            backtest.Slot(
                start + timedelta(minutes=45),
                import_kwh=0.0,
                export_kwh=backtest.WW_SLOT_KWH,
            ),
        ]

        result = backtest.allocate_ww_zero_import(slots)

        self.assertAlmostEqual(
            result["absorbableExportKWh"],
            2 * backtest.WW_SLOT_KWH,
            places=6,
        )
        self.assertAlmostEqual(
            slots[2].export_kwh,
            backtest.WW_SLOT_KWH,
            places=6,
        )

    def test_overlap_summary_exposes_competition_and_order_sensitivity(self):
        result = backtest.overlap_summary(
            ev_standalone_kwh=4.0,
            ww_standalone_kwh=3.0,
            ev_then_ww_kwh=5.5,
            ww_then_ev_kwh=5.0,
        )

        self.assertAlmostEqual(
            result["standaloneSumKWh"],
            7.0,
            places=6,
        )
        self.assertAlmostEqual(
            result["bestCombinedTwoOrderingsKWh"],
            5.5,
            places=6,
        )
        self.assertAlmostEqual(
            result["overlapAgainstBestTwoOrderingsKWh"],
            1.5,
            places=6,
        )
        self.assertAlmostEqual(
            result["orderSensitivityKWh"],
            0.5,
            places=6,
        )

    def test_battery_sequentially_moves_export_to_later_import(self):
        start = datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc)
        slots = [
            backtest.Slot(start, 0.0, 1.0),
            backtest.Slot(
                start + timedelta(minutes=15),
                0.0,
                1.0,
            ),
            backtest.Slot(
                start + timedelta(minutes=30),
                1.0,
                0.0,
            ),
            backtest.Slot(
                start + timedelta(minutes=45),
                1.0,
                0.0,
            ),
        ]

        result = backtest.simulate_battery(
            slots,
            capacity_kwh=5.0,
            max_power_w=5000.0,
            charge_efficiency=1.0,
            discharge_efficiency=1.0,
        )

        self.assertAlmostEqual(
            result["pvChargedFromOtherwiseExportKWh"],
            2.0,
            places=6,
        )
        self.assertAlmostEqual(
            result["gridImportAvoidedKWh"],
            2.0,
            places=6,
        )
        self.assertAlmostEqual(
            sum(slot.export_kwh for slot in slots),
            0.0,
            places=6,
        )
        self.assertAlmostEqual(
            sum(slot.import_kwh for slot in slots),
            0.0,
            places=6,
        )


    def test_ww_never_exceeds_modeled_daily_demand(self):
        # Monday 2026-09-21 has modeled demand 5.8 kWh.
        # 13 full boiler slots would otherwise total 6.175 kWh.
        start = datetime(2026, 9, 21, 7, 30, tzinfo=timezone.utc)
        slots = [
            backtest.Slot(
                start + timedelta(minutes=15 * i),
                import_kwh=0.0,
                export_kwh=backtest.WW_SLOT_KWH,
            )
            for i in range(13)
        ]

        result = backtest.allocate_ww_zero_import(slots)

        self.assertAlmostEqual(result["modeledDemandKWh"], 5.8, places=6)
        self.assertAlmostEqual(result["selectedRunKWh"], 5.8, places=6)
        self.assertAlmostEqual(result["absorbableExportKWh"], 5.8, places=6)


if __name__ == "__main__":
    unittest.main()
