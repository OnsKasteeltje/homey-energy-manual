#!/usr/bin/env python3
"""Synchronize the canonical Energy State contract with runtime data.

Same-major forward schema-version bumps and forward publisher-version bumps within
one publisher family are synchronized automatically. Major schema changes,
rollbacks, publisher-family changes and malformed publisher versions remain
fail-closed/manual.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "docs" / "data" / "energy-state-v2.json"
SCHEMA_PATH = ROOT / "docs" / "data" / "energy-state-v2.schema.json"
VERSION_RE = re.compile(r"^(\d+)\.(\d+)$")
PUBLISHER_RE = re.compile(r"^(?P<family>[A-Z0-9_]+)_V(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")


def parse_version(value: object, label: str) -> tuple[int, int]:
    if not isinstance(value, str):
        raise SystemExit(f"{label} must be a string, got {type(value).__name__}")
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise SystemExit(f"Invalid {label}: {value!r}; expected MAJOR.MINOR")
    return int(match.group(1)), int(match.group(2))


def parse_publisher(value: object, label: str) -> tuple[str, tuple[int, int, int]]:
    if not isinstance(value, str):
        raise SystemExit(f"{label} must be a string, got {type(value).__name__}")
    match = PUBLISHER_RE.fullmatch(value)
    if not match:
        raise SystemExit(
            f"Invalid {label}: {value!r}; expected FAMILY_VMAJOR.MINOR.PATCH, "
            "for example EM2_PUBLISHER_V1.0.11"
        )
    return match.group("family"), (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
    )


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
    runtime_publisher_family, runtime_publisher_tuple = parse_publisher(
        runtime_publisher, "runtime publisher_version"
    )
    canonical_publisher_family, canonical_publisher_tuple = parse_publisher(
        canonical_publisher, "canonical publisher_version"
    )

    if runtime_publisher_family != canonical_publisher_family:
        raise SystemExit(
            "Publisher family change requires an explicit contract migration: "
            f"runtime={runtime_publisher!r}, canonical={canonical_publisher!r}"
        )
    if runtime_publisher_tuple < canonical_publisher_tuple:
        raise SystemExit(
            "Runtime publisher version is older than canonical; refusing automatic rollback: "
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

    changed = False

    if runtime_tuple > canonical_tuple:
        if not isinstance(compatible_versions, list) or not all(isinstance(v, str) for v in compatible_versions):
            raise SystemExit("x-frontend-compatible-schema-versions must be a string list")

        normalized = set(compatible_versions)
        normalized.add(runtime_version)
        for version in normalized:
            parsed = parse_version(version, "frontend compatible schema version")
            if parsed[0] != runtime_tuple[0]:
                raise SystemExit(f"Cross-major frontend compatibility entry is not allowed: {version!r}")

        schema_meta["schema_version"]["const"] = runtime_version
        schema["x-frontend-compatible-schema-versions"] = sorted(
            normalized, key=lambda item: parse_version(item, item)
        )
        changed = True
        print(f"Energy State schema version synchronized: {canonical_version} -> {runtime_version}")

    if runtime_publisher_tuple > canonical_publisher_tuple:
        schema_meta["publisher_version"]["const"] = runtime_publisher
        changed = True
        print(
            "Energy State publisher contract synchronized: "
            f"{canonical_publisher} -> {runtime_publisher}"
        )

    if not changed:
        print(
            "Energy State contract already synchronized at "
            f"schema={runtime_version}, publisher={runtime_publisher}"
        )
        return False

    schema_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def main() -> None:
    sync_contract()


if __name__ == "__main__":
    main()
