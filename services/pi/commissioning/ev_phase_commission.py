#!/usr/bin/env python3
"""
One-shot Easee phase-mode commissioning tool.

Safety properties:
- refuses to send a phase command unless Homey reports target current 0 A,
  offered current ~0 A and charger power <= 250 W;
- asks Easee credentials interactively and keeps them in memory only;
- never prints access/refresh tokens or passwords;
- sends only the official Easee set_phase_mode command;
- confirms the resulting phase mode via Homey device settings;
- on failed 1P confirmation, best-effort restores locked 3P before exiting.

This tool is for manual commissioning only. It is not part of automatic control.
"""

import argparse
import getpass
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOMEY = "/home/jeroen/ems-homey-adapter/node_modules/.bin/homey"
HOMEY_DEVICE_ID = "4d0b6913-d940-474e-95d6-b43f194c4119"
EASEE_SERIAL = "ECHM6B9F"
API = "https://api.easee.com/api"
ZERO_POWER_MAX_W = 250.0
ZERO_OFFERED_MAX_A = 1.0
CONFIRM_TIMEOUT_S = 45
POLL_S = 3

MODE = {
    "1P": {"value": 1, "label": "Locked to single phase"},
    "3P": {"value": 3, "label": "Locked to three phase"},
}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def get_homey_device():
    env = os.environ.copy()
    env["PATH"] = "/opt/node-v24.20.0/bin:" + env.get("PATH", "")
    out = subprocess.check_output(
        [HOMEY, "api", "devices", "get-device", "--id", HOMEY_DEVICE_ID, "--json"],
        text=True,
        env=env,
    )
    return json.loads(out)


def cap(device, capability):
    obj = (device.get("capabilitiesObj") or {}).get(capability) or {}
    return obj.get("value")


def safety_snapshot(device):
    return {
        "targetA": _num(cap(device, "target_charger_current")),
        "offeredA": _num(cap(device, "measure_current.offered")),
        "powerW": _num(cap(device, "measure_power")),
        "charging": cap(device, "evcharger_charging"),
        "chargeState": cap(device, "evcharger_charging_state"),
        "phaseMode": (device.get("settings") or {}).get("phaseMode"),
    }


def assert_zero_current_safe(snapshot):
    if snapshot["targetA"] != 0:
        raise RuntimeError(f"PRECONDITION_TARGET_NOT_ZERO:{snapshot['targetA']}")
    if snapshot["offeredA"] is None or snapshot["offeredA"] > ZERO_OFFERED_MAX_A:
        raise RuntimeError(f"PRECONDITION_OFFERED_CURRENT_NOT_ZERO:{snapshot['offeredA']}")
    if snapshot["powerW"] is None or snapshot["powerW"] > ZERO_POWER_MAX_W:
        raise RuntimeError(f"PRECONDITION_POWER_NOT_ZERO:{snapshot['powerW']}")
    if snapshot["charging"] is True:
        raise RuntimeError("PRECONDITION_CHARGING_STILL_TRUE")
    if str(snapshot["chargeState"] or "").lower() != "plugged_in_paused":
        raise RuntimeError(f"PRECONDITION_SESSION_NOT_PAUSED:{snapshot['chargeState']}")


def post_json(url, payload, token=None):
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, application/octet-stream",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            return r.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read()
        raise RuntimeError(f"HTTP_{e.code}:{raw[:200].decode('utf-8', errors='replace')}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"NETWORK_ERROR:{e.reason}")


def authenticate(username, password):
    status, raw = post_json(
        f"{API}/accounts/login",
        {"userName": username, "password": password},
    )
    if status != 200:
        raise RuntimeError(f"AUTH_HTTP_{status}")
    data = json.loads(raw or b"{}")
    token = data.get("accessToken")
    if not token:
        raise RuntimeError("AUTH_ACCESS_TOKEN_MISSING")
    return token


def set_phase_mode(token, value):
    status, _ = post_json(
        f"{API}/chargers/{EASEE_SERIAL}/commands/set_phase_mode",
        {"phaseMode": int(value)},
        token=token,
    )
    if status != 200:
        raise RuntimeError(f"SET_PHASE_HTTP_{status}")


def wait_for_phase(expected_label, timeout_s=CONFIRM_TIMEOUT_S):
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        d = get_homey_device()
        last = (d.get("settings") or {}).get("phaseMode")
        print(f"readback phaseMode: {last}")
        if last == expected_label:
            return True, d
        time.sleep(POLL_S)
    return False, get_homey_device()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["1P", "3P"])
    args = ap.parse_args()

    desired = MODE[args.mode]
    print("=== PRECONDITION ===")
    before = get_homey_device()
    snap = safety_snapshot(before)
    print(json.dumps(snap, indent=2))
    assert_zero_current_safe(snap)

    username = input("Easee username/email: ").strip()
    if not username:
        raise RuntimeError("EASEE_USERNAME_MISSING")
    password = getpass.getpass("Easee password: ")
    if not password:
        raise RuntimeError("EASEE_PASSWORD_MISSING")

    print("\nAuthenticating with Easee Cloud...")
    token = authenticate(username, password)

    print(f"Sending set_phase_mode -> {args.mode} ({desired['value']})")
    set_phase_mode(token, desired["value"])

    print(f"Waiting for Homey readback: {desired['label']}")
    ok, after = wait_for_phase(desired["label"])
    if ok:
        print("\nPASS")
        print(json.dumps(safety_snapshot(after), indent=2))
        return 0

    if args.mode == "1P":
        print("\n1P confirmation failed; best-effort restoring locked 3P...")
        try:
            set_phase_mode(token, MODE["3P"]["value"])
            restored, final = wait_for_phase(MODE["3P"]["label"], timeout_s=30)
            print("restore3P:", "PASS" if restored else "NOT_CONFIRMED")
            print(json.dumps(safety_snapshot(final), indent=2))
        except Exception as exc:
            print(f"restore3P: ERROR:{exc}")

    raise RuntimeError(f"PHASE_CONFIRM_TIMEOUT:{desired['label']}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nABORTED", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
