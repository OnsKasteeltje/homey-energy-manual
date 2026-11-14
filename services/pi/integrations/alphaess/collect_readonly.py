#!/usr/bin/env python3
"""AlphaESS VitaPower Modbus TCP observation (FC03 only; no control path).

Run manually from the repository checkout. Optional history archive requires an
explicit --archive-db path to an EXISTING EMS history database. No timer/service
or automatic deployment is part of V0.1.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import sqlite3
import struct
import sys

SCHEMA = "EMS_PI_ALPHAESS_MODBUS_READONLY_V0.1"
UNIT_ID = 85
MAX_PDU_LENGTH = 253
DEVICE_KEY = "battery_alphaess"


class ModbusReadError(ValueError):
    """An invalid or rejected read-only Modbus reply."""


def recv_exact(sock, count):
    result = bytearray()
    while len(result) < count:
        part = sock.recv(count - len(result))
        if not part:
            raise ModbusReadError("INCOMPLETE_RESPONSE")
        result.extend(part)
    return bytes(result)


def read_holding(sock, tx, start, count):
    if not (1 <= count <= 125 and 0 <= start <= 65535 - count + 1):
        raise ValueError("INVALID_READ_RANGE")
    # Modbus TCP MBAP + function 03 (Read Holding Registers), NEVER write FCs.
    sock.sendall(struct.pack(">HHHBBHH", tx, 0, 6, UNIT_ID, 3, start, count))
    header = recv_exact(sock, 7)
    tid, protocol, length, unit = struct.unpack(">HHHB", header)
    if tid != tx or protocol != 0 or unit != UNIT_ID or not 2 <= length <= MAX_PDU_LENGTH:
        raise ModbusReadError("INVALID_MBAP")
    payload = recv_exact(sock, length - 1)
    if payload[0] == 0x83:
        raise ModbusReadError("MODBUS_EXCEPTION")
    if (len(payload) != 2 + count * 2 or payload[0] != 3
            or payload[1] != count * 2):
        raise ModbusReadError("INVALID_FUNCTION_OR_LENGTH")
    return struct.unpack(">" + "H" * count, payload[2:])


def signed16(word):
    return struct.unpack(">h", struct.pack(">H", word))[0]


def signed32(hi, lo):
    return struct.unpack(">i", struct.pack(">HH", hi, lo))[0]


def unsigned32(hi, lo):
    return (hi << 16) | lo


def decode(battery, ac):
    """Decode fixed register blocks; never infer energy when validation fails."""
    if len(battery) != 37 or len(ac) != 2:
        raise ValueError("INVALID_BLOCK_SIZE")

    def reg(address):
        return battery[address - 0x0102]

    data = {
        "socPct": reg(0x0102) / 10,
        "moduleCount": reg(0x0118),
        "nominalCapacityKWh": reg(0x0119) / 10,
        "sohPct": reg(0x011B) / 10,
        "chargeTotalKWh": unsigned32(reg(0x0120), reg(0x0121)) / 10,
        "dischargeTotalKWh": unsigned32(reg(0x0122), reg(0x0123)) / 10,
        "gridChargeReportedKWh": unsigned32(reg(0x0124), reg(0x0125)) / 10,
        "batteryDcPowerW": signed16(reg(0x0126)),
        "inverterAcPowerW": signed32(*ac),
    }
    if not (0 <= data["socPct"] <= 100 and 1 <= data["moduleCount"] <= 12
            and 0 < data["nominalCapacityKWh"] <= 64
            and 0 <= data["sohPct"] <= 100):
        raise ValueError("INVALID_BATTERY_IDENTITY")
    if abs(data["batteryDcPowerW"]) > 10000 or abs(data["inverterAcPowerW"]) > 10000:
        raise ValueError("INVALID_POWER")
    # The source's grid-charge counter was 49.3 kWh with total charge 44.4;
    # keep it observable but NEVER treat it as a validated source of energy.
    return data


def collect(host, timeout=5):
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = {
        "schema": SCHEMA,
        "sampledAtUtc": timestamp,
        "source": "ALPHAESS_LOCAL_MODBUS_TCP",
        "readOnly": True,
        "controlWrites": False,
        "eligibleForControl": False,
        "eligibleForHouseBalance": False,
        "quality": "UNAVAILABLE",
        "errorCode": None,
        "measurements": None,
        "caveats": {"gridChargeReportedKWh": "UNVERIFIED_SEMANTICS",
                    "acEnergyKWh": "NOT_MEASURED_BY_THIS_SNAPSHOT"},
    }
    try:
        # Two reads on ONE TCP connection: device can refuse rapid reconnects.
        with socket.create_connection((host, 502), timeout=timeout) as sock:
            sock.settimeout(timeout)
            battery = read_holding(sock, 1, 0x0102, 37)
            ac = read_holding(sock, 2, 0x040C, 2)
        result["measurements"] = decode(battery, ac)
        result["quality"] = "OBSERVED_PI_POLL_TIME"
        result["sampledAtUtc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    except (OSError, ModbusReadError, ValueError) as exc:
        result["errorCode"] = (
            str(exc) if isinstance(exc, (ModbusReadError, ValueError))
            else "MODBUS_CONNECTION_UNAVAILABLE"
        )
    return result


ARCHIVE_METRICS = {
    "soc_pct": ("socPct", "%"),
    "module_count": ("moduleCount", None),
    "nominal_capacity_kwh": ("nominalCapacityKWh", "kWh"),
    "soh_pct": ("sohPct", "%"),
    "battery_dc_power_w": ("batteryDcPowerW", "W"),
    "battery_ac_power_w": ("inverterAcPowerW", "W"),
    "battery_charge_total_kwh": ("chargeTotalKWh", "kWh"),
    "battery_discharge_total_kwh": ("dischargeTotalKWh", "kWh"),
}


def archive_snapshot(path, snapshot):
    """Explicit opt-in. Append source-isolated rows to existing EMS history."""
    if snapshot["quality"] != "OBSERVED_PI_POLL_TIME":
        raise ValueError("REFUSE_ARCHIVE_INVALID_SAMPLE")
    db = Path(path)
    if not db.is_file():
        raise FileNotFoundError("EXISTING_EMS_HISTORY_REQUIRED")
    con = sqlite3.connect(f"file:{db}?mode=rw", uri=True, timeout=5)
    try:
        con.execute("PRAGMA busy_timeout=5000")
        with con:
            row = con.execute("SELECT id FROM devices WHERE device_key=?", (DEVICE_KEY,)).fetchone()
            if row:
                device_id = row[0]
            else:
                con.execute("""INSERT INTO devices
                    (source, source_device_id, device_key, name, device_type)
                    VALUES ('alphaess_modbus_tcp', 'alphaess:vitapower3600', ?,
                            'AlphaESS VitaPower 3600', 'battery')""", (DEVICE_KEY,))
                device_id = con.execute("SELECT id FROM devices WHERE device_key=?", (DEVICE_KEY,)).fetchone()[0]
            written = 0
            for key, (field, unit) in ARCHIVE_METRICS.items():
                con.execute("""INSERT OR IGNORE INTO metrics
                    (metric_key, unit, value_type, description)
                    VALUES (?, ?, 'number', 'AlphaESS read-only SHADOW evidence')""", (key, unit))
                metric_id = con.execute("SELECT id FROM metrics WHERE metric_key=?", (key,)).fetchone()[0]
                cur = con.execute("""INSERT OR IGNORE INTO measurements
                    (ts_utc, device_id, metric_id, value_real, quality, source_resolution_seconds)
                    VALUES (?, ?, ?, ?, 'observed', 60)""", (
                        snapshot["sampledAtUtc"], device_id, metric_id,
                        float(snapshot["measurements"][field]),
                    ))
                written += cur.rowcount
        return written
    finally:
        con.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="AlphaESS VitaPower read-only Modbus observation")
    parser.add_argument("--host", required=True, help="Private LAN IP of VitaPower")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--archive-db", type=Path, help="Opt-in: append to existing EMS SQLite")
    args = parser.parse_args(argv)
    if not 0.5 <= args.timeout <= 20:
        parser.error("timeout must be between 0.5 and 20 seconds")
    result = collect(args.host, args.timeout)
    if args.archive_db and result["quality"] == "OBSERVED_PI_POLL_TIME":
        try:
            result["archivedRows"] = archive_snapshot(args.archive_db, result)
        except (OSError, sqlite3.Error, ValueError):
            result["archiveStatus"] = "FAILED"
            result["archiveErrorCode"] = "ARCHIVE_UNAVAILABLE"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["quality"] == "OBSERVED_PI_POLL_TIME" else 1


if __name__ == "__main__":
    sys.exit(main())
