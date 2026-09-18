#!/usr/bin/env python3
"""Build the isolated Frontend V2 preview into the MkDocs site tree.

MkDocs treats unknown files below docs/ as static assets, but source files that
arrive only during the workflow are not a reliable publication boundary.
Therefore V2 is staged directly into site/v2 *after* mkdocs build.
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend"
TARGET = ROOT / "site" / "v2"

if not (SOURCE / "live" / "index.html").is_file():
    raise SystemExit("Frontend V2 Live source missing")

if TARGET.exists():
    shutil.rmtree(TARGET)
TARGET.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(SOURCE, TARGET)

print(f"Frontend V2 preview staged: {TARGET / 'live' / 'index.html'}")
