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
    validate_dependency_lock()
    validate_frontend_version()
    print("Repository validation OK")


if __name__ == "__main__":
    main()
