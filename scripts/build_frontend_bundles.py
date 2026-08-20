#!/usr/bin/env python3
"""Build deterministic frontend bundles for MkDocs.

The source files stay separate for maintainability and rollback. The generated
bundles preserve the exact source order previously declared in mkdocs.yml.
Bump BUNDLE_VERSION whenever the active frontend source set changes so deployed
clients receive an explicit cache-busting asset URL.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
BUNDLE_VERSION = "v3"

JS_SOURCES = [
    "javascripts/energy-core-v2-adapter-v2.8.86.js",
    "javascripts/em-v2-health-v2.0.4.js",
    "javascripts/homey-status-v2.js",
    "javascripts/pv-phase-24h.js",
    "javascripts/live-energy-model-v1.js",
    "javascripts/live-energy-v2.8.85.js",
    "javascripts/live-energy-inactive-zero-v2.8.52.js",
    "javascripts/live-energy-balance-guard-v2.8.77.js",
    "javascripts/live-energy-measured-house-fallback-v2.8.79.js",
    "javascripts/live-energy-overig-detail-v2.8.78.js",
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
    "javascripts/energy-history-day-picker-layout-v2.8.83.js",
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


def main() -> None:
    build_bundle(JS_SOURCES, f"javascripts/frontend-bundle-{BUNDLE_VERSION}.js", "js")
    build_bundle(CSS_SOURCES, f"stylesheets/frontend-bundle-{BUNDLE_VERSION}.css", "css")


if __name__ == "__main__":
    main()
