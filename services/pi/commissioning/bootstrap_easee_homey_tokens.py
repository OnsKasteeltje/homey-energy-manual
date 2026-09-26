#!/usr/bin/env python3
"""
Bootstrap Easee cloud tokens into private Homey Logic variables.

- Prompts for Easee username/password locally.
- Exchanges credentials once for access + rotating refresh token.
- Stores only tokens + expiry timestamp in Homey Logic.
- Never prints token values or the password.
- Does not store username/password.

Required Homey CLI:
  /home/jeroen/ems-homey-adapter/node_modules/.bin/homey
"""

import getpass
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

HOMEY = "/home/jeroen/ems-homey-adapter/node_modules/.bin/homey"
LOGIN_URL = "https://api.easee.com/api/accounts/login"

VARS = {
    "EM2_Easee_Access_Token": None,
    "EM2_Easee_Refresh_Token": None,
    "EM2_Easee_Access_Expires_At": None,
}


def post_json(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            return r.status, json.loads(raw or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP_{e.code}:{body[:200]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"NETWORK_ERROR:{e.reason}")


def homey(*args):
    env = os.environ.copy()
    env["PATH"] = "/opt/node-v24.20.0/bin:" + env.get("PATH", "")
    return subprocess.check_output([HOMEY, *args], text=True, env=env)


def upsert_string(name, value, existing):
    found = next((v for v in existing.values() if v.get("name") == name), None)
    body = json.dumps({"value": value})
    if found:
        homey("api", "logic", "update-variable", "--id", found["id"], "--body", body)
        return found["id"]
    create = json.dumps({"name": name, "type": "string", "value": value})
    raw = homey("api", "logic", "create-variable", "--body", create, "--json")
    created = json.loads(raw)
    return created.get("id")


def main():
    username = input("Easee username/email: ").strip()
    if not username:
        raise RuntimeError("EASEE_USERNAME_MISSING")
    password = getpass.getpass("Easee password: ")
    if not password:
        raise RuntimeError("EASEE_PASSWORD_MISSING")

    print("Authenticating with Easee Cloud...")
    status, data = post_json(LOGIN_URL, {"userName": username, "password": password})
    if status != 200:
        raise RuntimeError(f"AUTH_HTTP_{status}")

    access = data.get("accessToken")
    refresh = data.get("refreshToken")
    expires_in = data.get("expiresIn")
    if not access or not refresh:
        raise RuntimeError("TOKEN_PAIR_MISSING")
    try:
        expires_in = int(expires_in)
    except (TypeError, ValueError):
        raise RuntimeError("TOKEN_EXPIRY_INVALID")

    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in - 60))
    ).isoformat().replace("+00:00", "Z")

    existing = json.loads(homey("api", "logic", "get-variables", "--json"))
    values = {
        "EM2_Easee_Access_Token": access,
        "EM2_Easee_Refresh_Token": refresh,
        "EM2_Easee_Access_Expires_At": expires_at,
    }

    ids = {}
    for name, value in values.items():
        ids[name] = upsert_string(name, value, existing)

    print("PASS: Easee tokens stored in private Homey Logic.")
    print("Stored variables:")
    for name in values:
        print(f"- {name}: {ids.get(name) or 'updated'}")
    print("Username/password were not stored.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nABORTED", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
