#!/usr/bin/env python3
"""Build the isolated Frontend V2 preview into MkDocs static output."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend"
TARGET = ROOT / "docs" / "v2"

if not (SOURCE / "live" / "index.html").is_file():
    raise SystemExit("Frontend V2 Live source missing")

if TARGET.exists():
    shutil.rmtree(TARGET)
shutil.copytree(SOURCE, TARGET)

print(f"Frontend V2 preview built: {TARGET / 'live' / 'index.html'}")
