#!/usr/bin/env python3

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

OWNER = "OnsKasteeltje"
REPO = "homey-energy-manual"
BRANCH = "main"
TARGET = "docs/data/energy-planner-shadow-pi.json"

SOURCE = Path("/home/jeroen/ems/data/energy-planner-shadow-pi.json")
TOKEN_FILE = Path("/home/jeroen/ems/secrets/github-planner-token")

if not SOURCE.exists():
    raise SystemExit(f"FAIL: source missing: {SOURCE}")

if not TOKEN_FILE.exists():
    raise SystemExit(f"FAIL: token missing: {TOKEN_FILE}")

token = TOKEN_FILE.read_text().strip()
if not token:
    raise SystemExit("FAIL: token empty")

payload = json.loads(SOURCE.read_text())
content = base64.b64encode(
    (json.dumps(payload, indent=2) + "\n").encode()
).decode()

url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{TARGET}"

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "EMS-Pi-Planner-Publisher",
}

def request(method, url, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        if e.code == 404:
            return 404, None
        raise SystemExit(f"FAIL: GitHub HTTP {e.code}: {text[:300]}")

status, current = request("GET", f"{url}?ref={BRANCH}")
sha = current.get("sha") if status == 200 and current else None

body = {
    "message": "chore: publish Pi Planner shadow snapshot",
    "content": content,
    "branch": BRANCH,
}
if sha:
    body["sha"] = sha

status, result = request("PUT", url, body)

if status not in (200, 201):
    raise SystemExit(f"FAIL: unexpected GitHub status {status}")

print("PASS: Pi Planner shadow published")
print("target:", TARGET)
print("commit:", result.get("commit", {}).get("sha"))
