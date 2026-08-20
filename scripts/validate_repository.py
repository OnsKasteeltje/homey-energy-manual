#!/usr/bin/env python3
"""Fail-fast repository validation used by CI before the MkDocs deployment."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ENERGY_SCHEMA_PATH = DOCS / "data" / "energy-state-v2.schema.json"


def validate_python() -> None:
    for directory in (ROOT / "scripts", ROOT / "tests"):
        for path in sorted(directory.glob("*.py")):
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


def energy_contract() -> tuple[str, str, str, list[str]]:
    schema_doc = load_json(ENERGY_SCHEMA_PATH)
    if not isinstance(schema_doc, dict):
        raise SystemExit("energy-state-v2.schema.json must contain a JSON object")
    try:
        meta_props = schema_doc["properties"]["meta"]["properties"]
        schema_version = meta_props["schema_version"]["const"]
        publisher_version = meta_props["publisher_version"]["const"]
        compatible_major = schema_doc["x-frontend-compatible-major"]
        compatible_versions = schema_doc["x-frontend-compatible-schema-versions"]
    except (KeyError, TypeError) as exc:
        raise SystemExit(f"Canonical Energy State contract is incomplete: {exc}") from exc
    if not all(isinstance(v, str) and v for v in (schema_version, publisher_version, compatible_major)):
        raise SystemExit("Canonical Energy State contract contains invalid scalar values")
    if not isinstance(compatible_versions, list) or not all(isinstance(v, str) for v in compatible_versions):
        raise SystemExit("Canonical Energy State compatibility list is invalid")
    if schema_version not in compatible_versions:
        raise SystemExit("Canonical schema version is missing from frontend compatibility list")
    if schema_version.split(".", 1)[0] != compatible_major:
        raise SystemExit("Frontend compatible major does not match canonical schema major")
    return schema_version, publisher_version, compatible_major, compatible_versions


def validate_energy_state() -> None:
    path = DOCS / "data" / "energy-state-v2.json"
    raw = load_json(path)
    if not isinstance(raw, dict):
        raise SystemExit("energy-state-v2.json must contain a JSON object")

    expected_schema, expected_publisher, _, _ = energy_contract()
    meta = require(raw, "meta", dict, "root")
    schema = require(meta, "schema_version", str, "meta")
    if schema != expected_schema:
        raise SystemExit(
            f"Energy State schema drift: runtime={schema!r}, canonical={expected_schema!r}. "
            "Update energy-state-v2.schema.json and frontend contract in the same change."
        )
    publisher = require(meta, "publisher_version", str, "meta")
    if publisher != expected_publisher:
        raise SystemExit(
            f"Energy State publisher drift: runtime={publisher!r}, canonical={expected_publisher!r}. "
            "Update the canonical contract together with the publisher."
        )

    for field in ("generated_at", "heartbeat_at", "control_mode"):
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

    loads = require(raw, "loads", dict, "root")
    quooker = require(loads, "quooker", dict, "loads")
    require(quooker, "active", bool, "loads.quooker")
    require(quooker, "switch_on", bool, "loads.quooker")
    require(quooker, "power_w", (int, float), "loads.quooker")
    require(quooker, "status", str, "loads.quooker")
    require(quooker, "source", str, "loads.quooker")
    require(quooker, "fresh", bool, "loads.quooker")
    if quooker["source"] != "HOMEY_SWITCH_PLUS_P1_L3":
        raise SystemExit(
            "Unsupported loads.quooker.source: "
            f"{quooker['source']!r}; expected 'HOMEY_SWITCH_PLUS_P1_L3'"
        )
    if quooker["status"] not in {"OFF", "ON_IDLE", "HEATING", "STALE"}:
        raise SystemExit(f"Unsupported loads.quooker.status: {quooker['status']!r}")

    revisions = {meta["state_revision"], meta["decision_revision"], meta["shadow_revision"]}
    if len(revisions) != 1:
        raise SystemExit(
            "energy-state-v2.json is not revision-consistent: "
            f"state={meta['state_revision']} decision={meta['decision_revision']} shadow={meta['shadow_revision']}"
        )


def requirement_lines(path: Path) -> set[str]:
    return {
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def validate_dependency_lock() -> None:
    lock = requirement_lines(ROOT / "requirements.lock")
    expected_direct = requirement_lines(ROOT / "requirements.txt") | requirement_lines(ROOT / "requirements-dev.txt")
    missing = sorted(expected_direct - lock)
    if missing:
        raise SystemExit(f"requirements.lock mist directe pins: {', '.join(missing)}")

    mkdocs_config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8").lower()
    if "pymdownx.snippets" in mkdocs_config:
        raise SystemExit("pymdownx.snippets is geblokkeerd zolang de locked PyMdown-lijn kwetsbaar is")


def validate_frontend_version() -> None:
    version = (ROOT / "frontend-version.txt").read_text(encoding="utf-8").strip()
    if not (version.startswith("v") and version[1:].isdigit()):
        raise SystemExit(f"Ongeldige frontend-version.txt: {version!r}")


def main() -> None:
    validate_python()
    validate_all_json()
    energy_contract()
    validate_energy_state()
    validate_dependency_lock()
    validate_frontend_version()
    print("Repository validation OK")


if __name__ == "__main__":
    main()
