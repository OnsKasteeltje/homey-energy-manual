#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOMEY_PROJECT = Path("/home/jeroen/ems-homey-adapter")
HOMEY_CLI = HOMEY_PROJECT / "node_modules/.bin/homey"
NODE_PATH = "/opt/node-v24.20.0/bin"

BACKUP_DIR = Path("/home/jeroen/ems/backups/homey-flows")


def canonical(flow):
    """
    Canonical representation for hashing/diffing.
    Ignore nothing yet: exact live object is authoritative.
    """
    return json.dumps(
        flow,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256(flow):
    return hashlib.sha256(
        canonical(flow).encode("utf-8")
    ).hexdigest()


def read_live(flow_id):
    env = os.environ.copy()
    env["PATH"] = NODE_PATH + ":" + env.get("PATH", "")

    cmd = [
        str(HOMEY_CLI),
        "api",
        "flow",
        "get-advanced-flow",
        "--id",
        flow_id,
        "--json",
    ]

    r = subprocess.run(
        cmd,
        cwd=HOMEY_PROJECT,
        env=env,
        text=True,
        capture_output=True,
    )

    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip()

        if "429" in msg:
            raise RuntimeError(
                "Homey rate limit 429; stopped without retry"
            )

        raise RuntimeError(
            f"Homey read failed: {msg[:500]}"
        )

    return json.loads(r.stdout)


def backup_live(flow):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    flow_id = flow.get("id", "unknown")
    stamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    path = BACKUP_DIR / f"{flow_id}.{stamp}.json"

    path.write_text(
        json.dumps(
            flow,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    return path


def load_candidate(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description="Read-only Homey Advanced Flow auditor"
    )

    parser.add_argument(
        "--id",
        required=True,
        help="Homey Advanced Flow ID",
    )

    parser.add_argument(
        "--candidate",
        help="Optional candidate JSON for comparison",
    )

    args = parser.parse_args()

    try:
        live = read_live(args.id)
    except Exception as e:
        print(f"FAIL: {e}")
        return 2

    if live.get("id") != args.id:
        print("FAIL: returned flow ID does not match requested ID")
        return 2

    backup = backup_live(live)
    live_hash = sha256(live)

    print("PASS: live Advanced Flow audited")
    print("id      :", live.get("id"))
    print("name    :", live.get("name"))
    print("enabled :", live.get("enabled"))
    print("broken  :", live.get("broken"))
    print("cards   :", len(live.get("cards", {})))
    print("sha256  :", live_hash)
    print("backup  :", backup)

    if not args.candidate:
        print("candidate: not supplied")
        print("result   : LIVE_CAPTURE_ONLY")
        return 0

    candidate_path = Path(args.candidate)

    if not candidate_path.exists():
        print("FAIL: candidate file does not exist")
        return 2

    try:
        candidate = load_candidate(candidate_path)
    except Exception as e:
        print(f"FAIL: candidate JSON invalid: {e}")
        return 2

    candidate_hash = sha256(candidate)

    print()
    print("candidate:", candidate_path)
    print("sha256   :", candidate_hash)

    if canonical(live) == canonical(candidate):
        print("result   : MATCH")
        return 0

    print("result   : DIFF")

    live_keys = set(live)
    candidate_keys = set(candidate)

    if live_keys != candidate_keys:
        print(
            "keys live-only     :",
            sorted(live_keys - candidate_keys)
        )
        print(
            "keys candidate-only:",
            sorted(candidate_keys - live_keys)
        )

    for key in sorted(live_keys & candidate_keys):
        if live[key] != candidate[key]:
            if key == "cards":
                lc = live.get("cards", {})
                cc = candidate.get("cards", {})

                print(
                    "cards live/candidate:",
                    len(lc),
                    "/",
                    len(cc),
                )

                changed = sorted(
                    k for k in set(lc) | set(cc)
                    if lc.get(k) != cc.get(k)
                )

                print("changed card ids:", changed)
            else:
                print(f"changed field: {key}")

    # DIFF is not a tool failure.
    return 1


if __name__ == "__main__":
    sys.exit(main())
