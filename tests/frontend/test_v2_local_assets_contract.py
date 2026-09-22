#!/usr/bin/env python3
"""Ensure Frontend V2 pages never reference missing local CSS/JS assets."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path("frontend")
PAGES = ("live", "settings", "history", "planner", "pv-flex", "heating")

class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and "stylesheet" in attrs.get("rel", "").split():
            self.refs.append(attrs.get("href"))
        elif tag == "script" and attrs.get("src"):
            self.refs.append(attrs.get("src"))

for page in PAGES:
    index = ROOT / page / "index.html"
    parser = Assets()
    parser.feed(index.read_text(encoding="utf-8"))
    assert parser.refs, f"{page}: no local assets found"
    for ref in parser.refs:
        assert ref, f"{page}: empty asset reference"
        parsed = urlsplit(ref)
        if parsed.scheme or parsed.netloc or ref.startswith("//"):
            continue
        target = (index.parent / parsed.path).resolve()
        assert target.is_relative_to(ROOT.resolve()), f"{page}: asset escapes frontend root: {ref}"
        assert target.is_file(), f"{page}: missing local asset: {ref} -> {target}"

print("PASS: Frontend V2 local asset references exist")
