#!/usr/bin/env python3
"""Focused safety/decoding checks; no hardware/network writes."""
import importlib.util
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[3] / "services/pi/integrations/alphaess/collect_readonly.py"
spec = importlib.util.spec_from_file_location("alphaess_collect_readonly", SOURCE)
alpha = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alpha)


def reply(tx, words):
    data = struct.pack(">BB", 3, len(words) * 2) + struct.pack(">" + "H" * len(words), *words)
    return struct.pack(">HHHB", tx, 0, len(data) + 1, alpha.UNIT_ID) + data


def battery_words():
    words = [0] * 37
    def put(addr, value):
        words[addr - 0x0102] = value
    put(0x0102, 576)       # 57.6%
    put(0x0118, 2)
    put(0x0119, 80)        # 8.0 kWh
    put(0x011B, 1000)
    put(0x0120, 0)
    put(0x0121, 444)       # 44.4 kWh
    put(0x0122, 0)
    put(0x0123, 392)       # 39.2 kWh
    put(0x0124, 0)
    put(0x0125, 493)       # 49.3 kWh - unverified
    put(0x0126, 862)
    return words


class FakeSocket:
    def __init__(self, replies):
        self.buffer = b"".join(replies)
        self.sent = []
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return None
    def settimeout(self, *_):
        return None
    def sendall(self, data):
        self.sent.append(data)
    def recv(self, count):
        part, self.buffer = self.buffer[:count], self.buffer[count:]
        return part


class AlphaESSReadonlyTests(unittest.TestCase):
    def fake(self):
        return FakeSocket([reply(1, battery_words()), reply(2, [0, 798])])

    def test_one_connection_two_fc03_reads_and_app_correlated_values(self):
        fake = self.fake()
        with patch.object(alpha.socket, "create_connection", return_value=fake) as connect:
            output = alpha.collect("192.0.2.2")
        self.assertEqual(connect.call_count, 1)
        self.assertEqual([p[7] for p in fake.sent], [3, 3])
        self.assertEqual([struct.unpack(">H", p[8:10])[0] for p in fake.sent], [0x0102, 0x040C])
        self.assertEqual(output["quality"], "OBSERVED_PI_POLL_TIME")
        self.assertFalse(output["eligibleForControl"])
        self.assertFalse(output["eligibleForHouseBalance"])
        self.assertFalse(output["controlWrites"])
        m = output["measurements"]
        self.assertEqual(m["socPct"], 57.6)
        self.assertEqual(m["moduleCount"], 2)
        self.assertEqual(m["nominalCapacityKWh"], 8)
        self.assertEqual(m["sohPct"], 100)
        self.assertEqual(m["chargeTotalKWh"], 44.4)
        self.assertEqual(m["dischargeTotalKWh"], 39.2)
        self.assertEqual(m["gridChargeReportedKWh"], 49.3)
        self.assertEqual(m["batteryDcPowerW"], 862)
        self.assertEqual(m["inverterAcPowerW"], 798)

    def test_negative_power_decode_and_failed_connection_has_no_measurements(self):
        words = battery_words()
        words[0x0126 - 0x0102] = 65536 - 860
        self.assertEqual(alpha.decode(words, [65535, 65536 - 800])["batteryDcPowerW"], -860)
        self.assertEqual(alpha.decode(words, [65535, 65536 - 800])["inverterAcPowerW"], -800)
        with patch.object(alpha.socket, "create_connection", side_effect=ConnectionRefusedError):
            unavailable = alpha.collect("192.0.2.2")
        self.assertEqual(unavailable["quality"], "UNAVAILABLE")
        self.assertIsNone(unavailable["measurements"])

    def test_bad_reply_and_implausible_soc_fail_closed(self):
        invalid = self.fake()
        invalid.buffer = invalid.buffer[:0] + bytes([0xFF]) + invalid.buffer[1:]
        with patch.object(alpha.socket, "create_connection", return_value=invalid):
            self.assertIsNone(alpha.collect("192.0.2.2")["measurements"])
        words = battery_words()
        words[0] = 1200
        with patch.object(alpha.socket, "create_connection", return_value=FakeSocket([
                reply(1, words), reply(2, [0, 798])])):
            self.assertEqual(alpha.collect("192.0.2.2")["errorCode"], "INVALID_BATTERY_IDENTITY")

    def test_archive_requires_existing_db_and_is_idempotent_and_isolated(self):
        with patch.object(alpha.socket, "create_connection", return_value=self.fake()):
            snapshot = alpha.collect("192.0.2.2")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ems-history.sqlite"
            with self.assertRaises(FileNotFoundError):
                alpha.archive_snapshot(path, snapshot)
            with sqlite3.connect(path) as con:
                con.executescript("""
                CREATE TABLE devices (id INTEGER PRIMARY KEY, source TEXT,
                    source_device_id TEXT, device_key TEXT UNIQUE, name TEXT, device_type TEXT);
                CREATE TABLE metrics (id INTEGER PRIMARY KEY, metric_key TEXT UNIQUE,
                    unit TEXT, value_type TEXT, description TEXT);
                CREATE TABLE measurements (id INTEGER PRIMARY KEY, ts_utc TEXT,
                    device_id INTEGER, metric_id INTEGER, value_real REAL,
                    quality TEXT, source_resolution_seconds INTEGER,
                    UNIQUE(ts_utc, device_id, metric_id));
                """)
            self.assertEqual(alpha.archive_snapshot(path, snapshot), len(alpha.ARCHIVE_METRICS))
            self.assertEqual(alpha.archive_snapshot(path, snapshot), 0)
            with sqlite3.connect(path) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM devices").fetchone()[0], 1)
                self.assertEqual(con.execute("SELECT count(*) FROM measurements").fetchone()[0], len(alpha.ARCHIVE_METRICS))
                self.assertEqual(con.execute("SELECT count(*) FROM metrics WHERE metric_key LIKE 'battery_%'").fetchone()[0], 4)


if __name__ == "__main__":
    unittest.main()
