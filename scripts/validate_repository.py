#!/usr/bin/env python3
"""Fail-fast repository validation used by CI before the MkDocs deployment."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def validate_python() -> None:
    for path in sorted((ROOT / "scripts").glob("*.py")):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            raise SystemExit(f"Python syntax error in {path.relative_to(ROOT)}: {exc}") from exc


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc


def validate_all_json() -> None:
    for path in sorted(DOCS.rglob("*.json")):
        load_json(path)
    for path in sorted(ROOT.glob("*.json")):
        load_json(path)


def require(mapping: dict, key: str, expected_type: type | tuple[type, ...], context: str) -> object:
    if key not in mapping:
        raise SystemExit(f"Missing required field {context}.{key}")
    value = mapping[key]
    if not isinstance(value, expected_type):
        raise SystemExit(
            f"Invalid type for {context}.{key}: expected {expected_type}, got {type(value).__name__}"
        )
    return value


def validate_energy_state() -> None:
    path = DOCS / "data" / "energy-state-v2.json"
    raw = load_json(path)
    if not isinstance(raw, dict):
        raise SystemExit("energy-state-v2.json must contain a JSON object")

    meta = require(raw, "meta", dict, "root")
    schema = require(meta, "schema_version", str, "meta")
    if schema != "2.10":
        raise SystemExit(f"Unsupported energy-state schema: {schema!r}; expected '2.10'")

    for field in ("generated_at", "heartbeat_at", "publisher_version", "control_mode"):
        require(meta, field, str, "meta")
    for field in ("state_revision", "decision_revision", "shadow_revision"):
        require(meta, field, int, "meta")

    grid = require(raw, "grid", dict, "root")
    require(grid, "power_w", (int, float), "grid")

    pv = require(raw, "pv", dict, "root")
    require(pv, "total_w", (int, float), "pv")

    battery = require(raw, "battery", dict, "root")
    require(battery, "integrated", bool, "battery")

    balance = require(raw, "balance", dict, "root")
    gate = require(balance, "control_gate", dict, "balance")
    require(gate, "grid_measurement_valid", bool, "balance.control_gate")
    require(gate, "derived_house_balance_valid", bool, "balance.control_gate")

    # Revision equality is an architectural invariant for a publishable snapshot.
    revisions = {meta["state_revision"], meta["decision_revision"], meta["shadow_revision"]}
    if len(revisions) != 1:
        raise SystemExit(
            "energy-state-v2.json is not revision-consistent: "
            f"state={meta['state_revision']} decision={meta['decision_revision']} shadow={meta['shadow_revision']}"
        )


def main() -> None:
    validate_python()
    validate_all_json()
    validate_energy_state()
    print("Repository validation OK")


if __name__ == "__main__":
    main()
