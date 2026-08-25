#!/usr/bin/env python3
"""Synchronize the canonical Energy State minor version with runtime data.

This intentionally automates only same-major, forward schema-version bumps. Major
version changes, rollbacks and publisher changes remain fail-closed/manual.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "docs" / "data" / "energy-state-v2.json"
SCHEMA_PATH = ROOT / "docs" / "data" / "energy-state-v2.schema.json"
VERSION_RE = re.compile(r"^(\d+)\.(\d+)$")


def parse_version(value: object, label: str) -> tuple[int, int]:
    if not isinstance(value, str):
        raise SystemExit(f"{label} must be a string, got {type(value).__name__}")
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise SystemExit(f"Invalid {label}: {value!r}; expected MAJOR.MINOR")
    return int(match.group(1)), int(match.group(2))


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return value


def sync_contract(runtime_path: Path = RUNTIME_PATH, schema_path: Path = SCHEMA_PATH) -> bool:
    runtime = load_json(runtime_path)
    schema = load_json(schema_path)

    try:
        runtime_meta = runtime["meta"]
        schema_meta = schema["properties"]["meta"]["properties"]
        runtime_version = runtime_meta["schema_version"]
        canonical_version = schema_meta["schema_version"]["const"]
        runtime_publisher = runtime_meta["publisher_version"]
        canonical_publisher = schema_meta["publisher_version"]["const"]
        compatible_major = schema["x-frontend-compatible-major"]
        compatible_versions = schema["x-frontend-compatible-schema-versions"]
    except (KeyError, TypeError) as exc:
        raise SystemExit(f"Energy State contract is incomplete: {exc}") from exc

    runtime_tuple = parse_version(runtime_version, "runtime schema_version")
    canonical_tuple = parse_version(canonical_version, "canonical schema_version")
    compatible_major_tuple = parse_version(f"{compatible_major}.0", "frontend compatible major")

    if runtime_publisher != canonical_publisher:
        raise SystemExit(
            "Publisher drift is not auto-synced: "
            f"runtime={runtime_publisher!r}, canonical={canonical_publisher!r}"
        )
    if runtime_tuple[0] != canonical_tuple[0] or runtime_tuple[0] != compatible_major_tuple[0]:
        raise SystemExit(
            "Major Energy State version change requires an explicit contract migration: "
            f"runtime={runtime_version!r}, canonical={canonical_version!r}, compatible_major={compatible_major!r}"
        )
    if runtime_tuple < canonical_tuple:
        raise SystemExit(
            "Runtime Energy State version is older than canonical; refusing automatic rollback: "
            f"runtime={runtime_version!r}, canonical={canonical_version!r}"
        )
    if runtime_tuple == canonical_tuple:
        print(f"Energy State contract already synchronized at {runtime_version}")
        return False

    if not isinstance(compatible_versions, list) or not all(isinstance(v, str) for v in compatible_versions):
        raise SystemExit("x-frontend-compatible-schema-versions must be a string list")

    normalized = set(compatible_versions)
    normalized.add(runtime_version)
    for version in normalized:
        parsed = parse_version(version, "frontend compatible schema version")
        if parsed[0] != runtime_tuple[0]:
            raise SystemExit(f"Cross-major frontend compatibility entry is not allowed: {version!r}")

    schema_meta["schema_version"]["const"] = runtime_version
    schema["x-frontend-compatible-schema-versions"] = sorted(normalized, key=lambda item: parse_version(item, item))
    schema_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Energy State contract synchronized: {canonical_version} -> {runtime_version}")
    return True


def main() -> None:
    sync_contract()


if __name__ == "__main__":
    main()
