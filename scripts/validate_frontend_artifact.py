#!/usr/bin/env python3
"""Validate that frontend source, generated bundles and MkDocs asset refs agree.

Run *after* scripts/build_frontend_bundles.py. This catches the failure mode where
source files are correct on main while GitHub Pages still builds/serves an older
or incomplete bundle.
"""
from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
VERSION = (ROOT / "frontend-version.txt").read_text(encoding="utf-8").strip()
MKDOCS = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")

if not VERSION.startswith("v") or not VERSION[1:].isdigit():
    raise SystemExit(f"Invalid frontend version: {VERSION!r}")

config = runpy.run_path(str(ROOT / "scripts" / "build_frontend_bundles.py"), run_name="bundle_config")
js_sources = config["JS_SOURCES"]
css_sources = config["CSS_SOURCES"]

js_bundle_path = DOCS / "javascripts" / f"frontend-bundle-{VERSION}.js"
css_bundle_path = DOCS / "stylesheets" / f"frontend-bundle-{VERSION}.css"

for path in (js_bundle_path, css_bundle_path):
    if not path.is_file():
        raise SystemExit(f"Generated frontend bundle missing: {path.relative_to(ROOT)}")

js_bundle = js_bundle_path.read_text(encoding="utf-8")
css_bundle = css_bundle_path.read_text(encoding="utf-8")

for source in js_sources:
    marker = f"// source: {source}"
    if marker not in js_bundle:
        raise SystemExit(f"JavaScript bundle {VERSION} misses configured source: {source}")

for source in css_sources:
    marker = f"/* source: {source} */"
    if marker not in css_bundle:
        raise SystemExit(f"CSS bundle {VERSION} misses configured source: {source}")

expected_js_ref = f"javascripts/frontend-bundle-{VERSION}.js"
expected_css_ref = f"stylesheets/frontend-bundle-{VERSION}.css"
if expected_js_ref not in MKDOCS or expected_css_ref not in MKDOCS:
    raise SystemExit(
        "mkdocs.yml does not point to the generated frontend version: "
        f"expected {expected_js_ref!r} and {expected_css_ref!r}"
    )
if "__FRONTEND_VERSION__" in MKDOCS:
    raise SystemExit("mkdocs.yml still contains unresolved __FRONTEND_VERSION__ after bundle build")

# Current Live View publication contract. These checks deliberately fail closed:
# a build may not deploy if the first-class Quooker renderer is absent from the
# actual artifact even when the editable source file was changed correctly.
required_live_contract = {
    "Quooker consumer": "title:'Quooker'",
    "Quooker icon": "ico:'quooker'",
    "Homey switch status": "switch_on",
    "Heating status": "HEATING",
}
for label, token in required_live_contract.items():
    if token not in js_bundle:
        raise SystemExit(f"Frontend bundle {VERSION} violates Live View contract ({label}): missing {token!r}")

print(
    f"Frontend artifact OK: {VERSION}; "
    f"{len(js_sources)} JS sources, {len(css_sources)} CSS sources; MkDocs refs synchronized."
)
