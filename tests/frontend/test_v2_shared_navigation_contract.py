#!/usr/bin/env python3
"""Contract checks for the shared Frontend V2 main navigation."""
from pathlib import Path

PAGES = ("live", "settings", "history", "planner", "pv-flex", "heating", "ai")
NAV = Path("frontend/shared/navigation.js")
SHELL = Path("frontend/shared/styles/v2-shell.css")
CADDY = Path("deploy/caddy/ems-frontend-v2.Caddyfile")
nav = NAV.read_text()
shell = SHELL.read_text()
caddy = CADDY.read_text()

expected = (
    ("live", "Live"),
    ("settings", "Invoer"),
    ("history", "Historie"),
    ("planner", "Planner"),
    ("pv-flex", "Evaluatie"),
    ("heating", "Verwarming"),
    ("ai", "AI Analyse"),
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
    assert 'apple-mobile-web-app-capable' in html, f"{page}: iPhone web app metadata missing"
    assert 'apple-mobile-web-app-title' in html, f"{page}: iPhone web app title missing"

assert 'aria-current' in nav
assert 'aria-disabled' in nav
assert 'const MOBILE_PRIMARY = ["live", "settings", "history"]' in nav
assert 'ems-nav-mobile' in nav
assert 'ems-mobile-more-toggle' in nav
assert 'ems-mobile-more-sheet' in nav
assert 'document.body.append(dock, sheet)' in nav
assert 'env(safe-area-inset-bottom)' in shell
assert 'position:fixed' in shell
assert '.ems-mobile-dock' in shell
assert '.topbar nav.ems-main-nav{display:none}' in shell
assert '.ems-nav-desktop{display:none}' in shell
assert '@root path /' in caddy
assert 'redir @root /live/ 302' in caddy
print("PASS: Frontend V2 shared navigation contract")
