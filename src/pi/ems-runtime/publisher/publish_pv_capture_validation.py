#!/usr/bin/env python3

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path

OWNER = "OnsKasteeltje"
REPO = "homey-energy-manual"
BRANCH = "main"
TOKEN_FILE = Path("/home/jeroen/ems/secrets/github-planner-token")
SOURCES = {
    "docs/data/pv-capture-validation.json": Path("/home/jeroen/ems/data/pv-capture-validation.json"),
    "docs/data/pv-capture-history.json": Path("/home/jeroen/ems/data/pv-capture-history.json"),
}

if not TOKEN_FILE.exists():
    raise SystemExit(f"FAIL: token missing: {TOKEN_FILE}")
token = TOKEN_FILE.read_text().strip()
if not token:
    raise SystemExit("FAIL: token empty")

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "EMS-Pi-PV-Capture-Publisher",
}


def request(method, url, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        if e.code == 404:
            return 404, None
        raise SystemExit(f"FAIL: GitHub HTTP {e.code}: {text[:300]}")


for target, source in SOURCES.items():
    if not source.exists():
        raise SystemExit(f"FAIL: source missing: {source}")
    payload = json.loads(source.read_text())
    content = base64.b64encode((json.dumps(payload, indent=2) + "\n").encode()).decode()
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{target}"
    status, current = request("GET", f"{url}?ref={BRANCH}")
    body = {
        "message": "chore: publish daily PV capture validation",
        "content": content,
        "branch": BRANCH,
    }
    if status == 200 and current:
        body["sha"] = current.get("sha")
    status, result = request("PUT", url, body)
    if status not in (200, 201):
        raise SystemExit(f"FAIL: unexpected GitHub status {status} for {target}")
    print("PASS:", target, result.get("commit", {}).get("sha"))
