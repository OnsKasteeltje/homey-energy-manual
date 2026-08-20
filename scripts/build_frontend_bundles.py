#!/usr/bin/env python3
"""Build deterministic frontend bundles for MkDocs.

The source files stay separate for maintainability and rollback. The generated
bundles preserve source order. frontend-version.txt is the single source of
truth for the deployed bundle version; mkdocs.yml is synchronized at build time.
The Energy State JSON schema is the single source of truth for frontend schema
compatibility and is converted to a tiny generated JavaScript contract at build.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
VERSION_FILE = ROOT / "frontend-version.txt"
MKDOCS = ROOT / "mkdocs.yml"
ENERGY_SCHEMA = DOCS / "data" / "energy-state-v2.schema.json"
ENERGY_CONTRACT_JS = DOCS / "javascripts" / "energy-contract-v2.generated.js"
BUNDLE_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()
if not re.fullmatch(r"v\d+", BUNDLE_VERSION):
    raise ValueError(f"Ongeldige frontendversie: {BUNDLE_VERSION!r}")

JS_SOURCES = [
    "javascripts/energy-store-v1.js",
    "javascripts/energy-contract-v2.generated.js",
    "javascripts/energy-core-v2-adapter-v2.8.91.js",
    "javascripts/em-v2-health-v2.0.4.js",
    "javascripts/homey-status-v2.js",
    "javascripts/pv-phase-24h.js",
    "javascripts/live-energy-model-v2.js",
    "javascripts/live-energy-v2.8.85.js",
    "javascripts/live-energy-balance-guard-v2.8.77.js",
    "javascripts/live-energy-overig-detail-v2.8.88.js",
    "javascripts/live-energy-battery-integration-guard-v2.8.68.js",
    "javascripts/live-energy-appliance-state-v2.8.80.js",
    "javascripts/live-energy-consumption-bus-sync-v2.8.81.js",
    "javascripts/live-energy-laundry-model-v2.8.70.js",
    "javascripts/tesla-deadline-ui-v2.8.16.js",
    "javascripts/tesla-deadline-migration-v2.8.17.js",
    "javascripts/tesla-deadline-postsave-v2.8.18.js",
    "javascripts/tesla-deadline-status-v2.8.21.js",
    "javascripts/tesla-runtime-ui-v2.8.24.js",
    "javascripts/energy-history-v2.8.55.js",
    "javascripts/energy-history-events-v2.8.56.js",
    "javascripts/energy-history-tesla-quality-v2.8.37.js",
    "javascripts/energy-history-autorefresh-v2.8.57.js",
    "javascripts/energy-history-freshness-v2.8.58.js",
    "javascripts/energy-history-day-picker-layout-v2.8.89.js",
    "javascripts/home-architecture-v2.0.3.js",
    "javascripts/home-architecture-kpi-cleanup-v2.0.4.js",
    "javascripts/home-space-heating-v2.0.5.js",
    "javascripts/pwa-register-v2.0.15.js",
    "javascripts/app-shell-v2.0.18.js",
]

CSS_SOURCES = [
    "stylesheets/extra.css",
    "stylesheets/live-energy-v2.0.11.css",
    "stylesheets/live-energy-heating-focus-v2.0.14.css",
    "stylesheets/live-energy-dark-v2.0.15.css",
    "stylesheets/live-energy-concept-v2.0.17.css",
    "stylesheets/live-energy-consumption-segments-v2.0.18.css",
    "stylesheets/live-energy-overig-detail-v2.0.19.css",
    "stylesheets/live-energy-battery-integration-v2.0.20.css",
    "stylesheets/live-energy-mobile-fit-v2.0.21.css",
    "stylesheets/live-energy-device-icon-state-v2.0.22.css",
    "stylesheets/em-v2-health-v2.8.29.css",
    "stylesheets/tesla-deadline-v2.8.10.css",
    "stylesheets/tesla-deadline-v2.8.17.css",
    "stylesheets/tesla-baseline-audit-v2.8.23.css",
    "stylesheets/energy-history-v2.8.14.css",
    "stylesheets/energy-history-v2.8.35.css",
    "stylesheets/energy-history-v2.8.42.css",
    "stylesheets/energy-history-freshness-v2.8.58.css",
    "stylesheets/energy-history-day-picker-layout-v2.8.84.css",
    "stylesheets/app-refresh-v2.0.17.css",
    "stylesheets/home-architecture-v1.css",
]


def load_energy_contract() -> dict[str, object]:
    schema = json.loads(ENERGY_SCHEMA.read_text(encoding="utf-8"))
    meta_props = schema.get("properties", {}).get("meta", {}).get("properties", {})
    schema_version = meta_props.get("schema_version", {}).get("const")
    publisher_version = meta_props.get("publisher_version", {}).get("const")
    compatible_major = schema.get("x-frontend-compatible-major")
    compatible_versions = schema.get("x-frontend-compatible-schema-versions", [])
    if not isinstance(schema_version, str) or not re.fullmatch(r"\d+\.\d+", schema_version):
        raise ValueError("energy-state-v2.schema.json mist geldige meta.schema_version const")
    if not isinstance(publisher_version, str) or not publisher_version:
        raise ValueError("energy-state-v2.schema.json mist publisher_version const")
    if not isinstance(compatible_major, str) or not compatible_major.isdigit():
        raise ValueError("energy-state-v2.schema.json mist x-frontend-compatible-major")
    if not isinstance(compatible_versions, list) or not all(isinstance(v, str) for v in compatible_versions):
        raise ValueError("energy-state-v2.schema.json heeft ongeldige compatible schema versions")
    if schema_version not in compatible_versions:
        raise ValueError("actuele schema_version ontbreekt in frontend compatibility lijst")
    return {
        "schemaVersion": schema_version,
        "publisherVersion": publisher_version,
        "compatibleMajor": compatible_major,
        "compatibleVersions": compatible_versions,
    }


def generate_energy_contract_js() -> None:
    contract = load_energy_contract()
    payload = json.dumps(contract, separators=(",", ":"), ensure_ascii=False)
    ENERGY_CONTRACT_JS.write_text(
        "// Generated by scripts/build_frontend_bundles.py; do not edit manually.\n"
        f"window.EnergyStateContract=Object.freeze({payload});\n",
        encoding="utf-8",
    )
    print(f"Generated {ENERGY_CONTRACT_JS.relative_to(ROOT)} from {ENERGY_SCHEMA.relative_to(ROOT)}")


def build_bundle(sources: list[str], output: str, kind: str) -> None:
    chunks: list[str] = []
    for relative in sources:
        source = DOCS / relative
        if not source.is_file():
            raise FileNotFoundError(f"Frontend source ontbreekt: {source}")
        text = source.read_text(encoding="utf-8").rstrip()
        marker = f"// source: {relative}" if kind == "js" else f"/* source: {relative} */"
        chunks.append(f"{marker}\n{text}\n")

    target = DOCS / output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(chunks), encoding="utf-8")
    print(f"Built {target.relative_to(ROOT)} from {len(sources)} sources")


def sync_mkdocs_assets() -> None:
    text = MKDOCS.read_text(encoding="utf-8")
    text = re.sub(r"frontend-bundle-(?:v\d+|__FRONTEND_VERSION__)\.js", f"frontend-bundle-{BUNDLE_VERSION}.js", text)
    text = re.sub(r"frontend-bundle-(?:v\d+|__FRONTEND_VERSION__)\.css", f"frontend-bundle-{BUNDLE_VERSION}.css", text)
    MKDOCS.write_text(text, encoding="utf-8")
    print(f"Synced mkdocs.yml to frontend {BUNDLE_VERSION}")


def main() -> None:
    generate_energy_contract_js()
    build_bundle(JS_SOURCES, f"javascripts/frontend-bundle-{BUNDLE_VERSION}.js", "js")
    build_bundle(CSS_SOURCES, f"stylesheets/frontend-bundle-{BUNDLE_VERSION}.css", "css")
    sync_mkdocs_assets()


if __name__ == "__main__":
    main()
