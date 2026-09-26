#!/usr/bin/env python3
"""
Bootstrap Easee cloud tokens into private Homey Logic variables.

- Prompts for Easee username/password locally.
- Exchanges credentials once for access + rotating refresh token.
- Stores only tokens + expiry timestamp in Homey Logic.
- Never prints token values or the password.
- Does not store username/password.
- Does not enumerate all Homey Logic variables: the EMS installation contains
  large JSON variables and the Homey CLI can truncate that aggregate response.
- Persists only the three non-secret Homey variable IDs in a local registry so
  later bootstraps can update the exact variables directly.

Required Homey CLI:
  /home/jeroen/ems-homey-adapter/node_modules/.bin/homey
"""

import getpass
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOMEY = "/home/jeroen/ems-homey-adapter/node_modules/.bin/homey"
LOGIN_URL = "https://api.easee.com/api/accounts/login"
REGISTRY = Path("/home/jeroen/ems/data/easee-homey-token-variable-ids.json")

VAR_NAMES = (
    "EM2_Easee_Access_Token",
    "EM2_Easee_Refresh_Token",
    "EM2_Easee_Access_Expires_At",
)


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
    return subprocess.check_output(
        [HOMEY, *args],
        text=True,
        env=env,
        stderr=subprocess.STDOUT,
    )


def homey_json(*args):
    raw = homey(*args)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"HOMEY_JSON_INVALID:{args[0] if args else 'UNKNOWN'}:"
            f"line={exc.lineno}:col={exc.colno}:chars={len(raw)}"
        ) from exc


def body_file(payload):
    """Create a 0600 temp body file so tokens never appear in process argv."""
    fd, path = tempfile.mkstemp(prefix="ems-easee-homey-", suffix=".json")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        return path
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def homey_body(command, *, var_id=None, payload):
    path = body_file(payload)
    try:
        args = ["api", "logic", command]
        if var_id:
            args += ["--id", var_id]
        args += ["--body", f"@{path}"]
        if command == "create-variable":
            args += ["--json"]
        return homey(*args)
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def load_registry():
    if not REGISTRY.exists():
        return {}
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"TOKEN_VARIABLE_REGISTRY_INVALID:{exc}") from exc
    return {
        name: str(data.get(name) or "").strip()
        for name in VAR_NAMES
        if str(data.get(name) or "").strip()
    }


def save_registry(ids):
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY.with_suffix(".tmp")
    tmp.write_text(json.dumps(ids, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, REGISTRY)
    os.chmod(REGISTRY, 0o600)


def get_variable(var_id):
    try:
        return homey_json("api", "logic", "get-variable", "--id", var_id, "--json")
    except subprocess.CalledProcessError:
        return None


def ensure_string_variable(name, value, registry):
    var_id = registry.get(name)

    if var_id:
        existing = get_variable(var_id)
        if existing and existing.get("name") == name:
            homey_body(
                "update-variable",
                var_id=var_id,
                payload={"value": value},
            )
            return var_id

    # First install or stale registry entry. Create only this small variable;
    # never enumerate the complete Logic store.
    raw = homey_body(
        "create-variable",
        payload={"name": name, "type": "string", "value": value},
    )
    try:
        created = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"HOMEY_CREATE_VARIABLE_JSON_INVALID:{name}") from exc

    created_id = str(created.get("id") or "").strip()
    if not created_id:
        raise RuntimeError(f"HOMEY_CREATE_VARIABLE_ID_MISSING:{name}")
    return created_id


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

    values = {
        "EM2_Easee_Access_Token": access,
        "EM2_Easee_Refresh_Token": refresh,
        "EM2_Easee_Access_Expires_At": expires_at,
    }

    registry = load_registry()
    ids = dict(registry)

    for name in VAR_NAMES:
        ids[name] = ensure_string_variable(name, values[name], ids)
        # Save after every successful create/update so an interrupted first run
        # can resume by exact ID without creating duplicates.
        save_registry(ids)

    print("PASS: Easee tokens stored in private Homey Logic.")
    print("Stored variables:")
    for name in VAR_NAMES:
        print(f"- {name}: PRESENT ({ids[name]})")
    print(f"Variable ID registry: {REGISTRY}")
    print("Username/password were not stored.")
    print("Token values were not printed and were not passed in process arguments.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nABORTED", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
