#!/usr/bin/env python3
"""Fail-fast repository validation used by CI before the MkDocs deployment."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


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

    # PyMdown Extensions is currently required transitively by MkDocs Material.
    # Its snippets extension has a known path-containment issue in the locked line;
    # this project does not need snippets, so fail closed if it is ever enabled.
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
    validate_energy_state()
    validate_dependency_lock()
    validate_frontend_version()
    print("Repository validation OK")


if __name__ == "__main__":
    main()
