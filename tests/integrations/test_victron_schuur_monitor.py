"""Offline regressions for the read-only Victron schuur shadow collector."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[2] / "services/pi/integrations/victron/schuur_monitor.py"
spec = importlib.util.spec_from_file_location("victron_schuur_monitor", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeSocket:
    def __init__(self, reply):
        self.buffer = bytearray(reply)
        self.request = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def settimeout(self, _timeout):
        return None

    def sendall(self, data):
        self.request = data

    def recv(self, count):
        data = bytes(self.buffer[:count])
        del self.buffer[:count]
        return data


class SchuurMonitorTests(unittest.TestCase):
    def test_read_only_modbus_function_and_registers(self):
        values = (250, 0xFF9C, 150)
        pdu = bytes((3, 6)) + struct.pack(">3H", *values)
        response = struct.pack(">HHHB", 1, 0, len(pdu) + 1, 40) + pdu
        fake = FakeSocket(response)
        with patch.object(module.socket, "create_connection", return_value=fake):
            self.assertEqual(module.read_registers("192.0.2.1", 40), values)
        self.assertEqual(fake.request, struct.pack(">HHHBBHH", 1, 0, 6, 40, 3, 3900, 3))
        self.assertEqual(fake.request[7], 3)  # FC03 only, no Modbus write

    def test_l2_fail_closed_even_if_meter_reports_value(self):
        state = module.snapshot(
            (250, 500, 150), 40, "2026-11-01T13:00:00+00:00"
        )
        self.assertEqual(state["phases"]["L1"]["powerW"], 250)
        self.assertIsNone(state["phases"]["L1"]["currentA"])
        self.assertIsNone(state["phases"]["L3"]["currentA"])
        self.assertEqual(state["phases"]["L1"]["currentQuality"], "UNVERIFIED")
        self.assertIsNone(state["phases"]["L2"]["powerW"])
        self.assertIsNone(state["phases"]["L2"]["currentA"])
        self.assertIsNone(state["totals"]["powerW"])
        self.assertFalse(state["eligibleForControl"])
        self.assertFalse(state["eligibleForHouseBalance"])

    def test_modbus_exception_rejected(self):
        pdu = bytes((0x83, 0x02))
        response = struct.pack(">HHHB", 1, 0, len(pdu) + 1, 40) + pdu
        with patch.object(module.socket, "create_connection", return_value=FakeSocket(response)):
            with self.assertRaisesRegex(ValueError, "exception"):
                module.read_registers("192.0.2.1", 40)

    def test_sqlite_shadow_idempotent_and_no_l2_field(self):
        state = module.snapshot((250, 500, 150), 40,
                                "2026-11-01T13:00:00+00:00")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "shadow.sqlite"
            module.save_shadow_db(path, state)
            module.save_shadow_db(path, state)
            with sqlite3.connect(path) as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM victron_schuur_samples").fetchone()[0], 1
                )
                columns = [
                    row[1] for row in db.execute("PRAGMA table_info(victron_schuur_samples)")
                ]
                self.assertFalse(any("l2" in col for col in columns))
                self.assertFalse(any("current" in col for col in columns))


if __name__ == "__main__":
    unittest.main()
