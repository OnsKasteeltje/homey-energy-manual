#!/usr/bin/env python3
"""Victron Schuurmonitor V0.1 — read-only AC-load Modbus TCP shadow collector.

No writes to Modbus, canonical EMS history, planner, state, or actuators.
L2 is intentionally invalid pending physical meter inspection.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import sqlite3
import struct
import sys
import tempfile


REGISTER_START = 3900  # com.victronenergy.acload: L1/L2/L3 power
REGISTER_COUNT = 16    # 3900..3915; includes serial 3903..3909 (never decoded as current)
MODBUS_PORT = 502
MAX_PDU_LENGTH = 253


def receive_exact(sock: socket.socket, count: int) -> bytes:
    data = bytearray()
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise ConnectionError("Modbus TCP connection closed during reply")
        data.extend(chunk)
    return bytes(data)


def read_registers(host: str, unit_id: int, timeout: float = 3.0) -> tuple[int, ...]:
    """Read only: function code 03, registers 3900..3915. No Modbus writes."""
    request = struct.pack(">HHHBBHH", 1, 0, 6, unit_id, 3, REGISTER_START, REGISTER_COUNT)
    with socket.create_connection((host, MODBUS_PORT), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(request)
        header = receive_exact(sock, 7)
        transaction, protocol, length, response_unit = struct.unpack(">HHHB", header)
        if (transaction, protocol, response_unit) != (1, 0, unit_id):
            raise ValueError("Unexpected Modbus TCP response header")
        if not (2 <= length <= MAX_PDU_LENGTH):
            raise ValueError("Invalid Modbus TCP reply length")
        pdu = receive_exact(sock, length - 1)
    if pdu[0] == 0x83:
        raise ValueError(f"Victron Modbus exception code {pdu[1] if len(pdu) > 1 else 'unknown'}")
    if pdu[0] != 3 or len(pdu) != 2 + REGISTER_COUNT * 2 or pdu[1] != REGISTER_COUNT * 2:
        raise ValueError("Unexpected Modbus function, byte count or register quantity")
    return struct.unpack(">" + "H" * REGISTER_COUNT, pdu[2:])


def signed16(raw: int) -> int:
    return raw - 65536 if raw >= 32768 else raw


def snapshot(registers: tuple[int, ...], unit_id: int, observed_at: str | None = None) -> dict:
    if len(registers) != REGISTER_COUNT:
        raise ValueError("Exactly 16 AC-load registers are required")
    at = observed_at or datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    # 3900..3902 = phase powers (W).
    # 3903..3909 = 7 Modbus words of serial number ("HQ..." on this device).
    # 3910, 3912, 3914 = voltage, scale 10.
    # 3911, 3913, 3915 = signed current, scale 10.
    # All current values are diagnostic only until compared with the GX UI.
    watts = [signed16(x) for x in registers[0:3]]
    volts = [registers[i] / 10 for i in (10, 12, 14)]
    amps = [signed16(registers[i]) / 10 for i in (11, 13, 15)]
    return {
        "schema": "EMS_VICTRON_SCHUUR_SHADOW_V0.1",
        "observedAtUtc": at,
        "sourceService": "com.victronenergy.acload",
        "unitId": unit_id,
        "eligibleForControl": False,
        "eligibleForHouseBalance": False,
        "quality": "PARTIAL_L2_INVALID",
        "phases": {
            "L1": {"powerW": watts[0], "voltageV": volts[0], "currentA": amps[0], "currentQuality": "PENDING_GUI_COMPARISON", "quality": "OBSERVED"},
            "L2": {"powerW": None, "voltageV": None, "currentA": None, "currentQuality": "INVALID_PENDING_REPAIR", "quality": "INVALID_PENDING_REPAIR"},
            "L3": {"powerW": watts[2], "voltageV": volts[2], "currentA": amps[2], "currentQuality": "PENDING_GUI_COMPARISON", "quality": "OBSERVED"},
        },
        "totals": {"powerW": None, "importKWh": None, "exportKWh": None,
                   "quality": "INVALID_INCOMPLETE_PHASES"},
    }


def save_shadow_db(db_path: Path, state: dict) -> None:
    """Separate SHADOW database; never modify ems-history.sqlite."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS victron_schuur_samples (
              observed_at_utc TEXT PRIMARY KEY,
              unit_id INTEGER NOT NULL,
              l1_power_w INTEGER,
              l3_power_w INTEGER,
              quality TEXT NOT NULL
            )
        """)
        con.execute("""
            INSERT OR IGNORE INTO victron_schuur_samples
            (observed_at_utc, unit_id, l1_power_w,
             l3_power_w, quality)
            VALUES (?, ?, ?, ?, ?)
        """, (
            state["observedAtUtc"], state["unitId"],
            state["phases"]["L1"]["powerW"],
            state["phases"]["L3"]["powerW"],
            state["quality"],
        ))


def save_json_atomic(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".victron-schuur-",
            suffix=".tmp", delete=False
        ) as tmp:
            temp_name = tmp.name
            json.dump(state, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Cerbo GX LAN IP (not VM-3P75CT IP)")
    parser.add_argument("--unit-id", type=int, required=True,
                        help="Unit ID of com.victronenergy.acload in GX Available services")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--shadow-db", type=Path, help="Optional separate SQLite shadow archive")
    parser.add_argument("--json-out", type=Path, help="Optional private current-snapshot JSON")
    args = parser.parse_args(argv)
    if not 1 <= args.unit_id <= 247:
        parser.error("--unit-id must be in 1..247")
    if not 0 < args.timeout <= 30:
        parser.error("--timeout must be in (0,30]")
    try:
        registers = read_registers(args.host, args.unit_id, args.timeout)
        state = snapshot(registers, args.unit_id)
        if args.shadow_db:
            save_shadow_db(args.shadow_db, state)
        if args.json_out:
            save_json_atomic(args.json_out, state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"Victron Schuurmonitor: UNAVAILABLE: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
