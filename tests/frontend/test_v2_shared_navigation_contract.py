#!/usr/bin/env python3
"""Contract checks for the shared Frontend V2 main navigation."""
from pathlib import Path

PAGES = ("live", "settings", "history", "planner", "pv-flex", "heating")
NAV = Path("frontend/shared/navigation.js")
nav = NAV.read_text()

expected = (
    ("live", "Live"),
    ("settings", "Invoer"),
    ("history", "Historie"),
    ("planner", "Planner"),
    ("pv-flex", "PV & Flex"),
    ("heating", "Verwarming"),
    ("groups", "Groepen & fasen"),
)

for key, label in expected:
    assert f'key: "{key}"' in nav, key
    assert f'label: "{label}"' in nav, label

for page in PAGES:
    html = Path(f"frontend/{page}/index.html").read_text()
    assert html.count('data-ems-main-nav') == 1, page
    assert html.count('../shared/navigation.js') == 1, page
    mount = '<nav data-ems-main-nav aria-label="Hoofdnavigatie"></nav>'
    assert html.count(mount) == 1, f"{page}: navigation mount must be empty and unique"

assert 'aria-current' in nav
assert 'aria-disabled' in nav
print("PASS: Frontend V2 shared navigation contract")
