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


def canonical(obj):
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def writable(flow):
    return {
        "name": flow["name"],
        "enabled": bool(flow["enabled"]),
        "cards": flow["cards"],
    }


def sha256(obj):
    return hashlib.sha256(
        canonical(obj).encode("utf-8")
    ).hexdigest()


def run_homey(args):
    env = os.environ.copy()
    env["PATH"] = NODE_PATH + ":" + env.get("PATH", "")

    r = subprocess.run(
        [str(HOMEY_CLI)] + args,
        cwd=HOMEY_PROJECT,
        env=env,
        text=True,
        capture_output=True,
    )

    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip()

        if "429" in msg:
            raise RuntimeError("Homey rate limit 429; stopped without retry")

        raise RuntimeError(msg[:1000])

    return r.stdout


def read_live(flow_id):
    out = run_homey([
        "api",
        "flow",
        "get-advanced-flow",
        "--id",
        flow_id,
        "--json",
    ])

    return json.loads(out)


def backup(flow, label):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    flow_id = flow["id"]

    path = BACKUP_DIR / f"{flow_id}.{stamp}.{label}.json"

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


def deploy(flow_id, candidate_path):
    out = run_homey([
        "api",
        "flow",
        "update-advanced-flow",
        "--id",
        flow_id,
        "--body",
        f"@{candidate_path}",
        "--json",
    ])

    return json.loads(out)


def main():
    ap = argparse.ArgumentParser(
        description="Controlled Homey Advanced Flow deployer"
    )

    ap.add_argument("--id", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Actually write to Homey"
    )

    args = ap.parse_args()

    candidate_path = Path(args.candidate)

    if not candidate_path.exists():
        print("FAIL: candidate does not exist")
        return 2

    try:
        candidate = json.loads(
            candidate_path.read_text(encoding="utf-8")
        )
    except Exception as e:
        print(f"FAIL: candidate JSON invalid: {e}")
        return 2

    if candidate.get("id") != args.id:
        print("FAIL: candidate ID differs from requested flow ID")
        return 2

    try:
        live_before = read_live(args.id)
    except Exception as e:
        print(f"FAIL: live read failed: {e}")
        return 2

    if live_before.get("id") != args.id:
        print("FAIL: Homey returned unexpected flow ID")
        return 2

    before_hash = sha256(writable(live_before))
    candidate_hash = sha256(writable(candidate))

    print("flow      :", live_before.get("name"))
    print("id        :", args.id)
    print("enabled   :", live_before.get("enabled"))
    print("broken    :", live_before.get("broken"))
    print("cards     :", len(live_before.get("cards", {})))
    print("live hash :", before_hash)
    print("cand hash :", candidate_hash)

    if before_hash == candidate_hash:
        print("result    : MATCH — nothing to deploy")
        return 0

    pre_backup = backup(live_before, "predeploy")
    print("backup    :", pre_backup)
    print("result    : DIFF")

    if not args.apply:
        print("mode      : DRY-RUN")
        print("write     : BLOCKED")
        return 1

    print("mode      : APPLY")

    payload_path = candidate_path.with_suffix(candidate_path.suffix + ".payload")
    payload_path.write_text(
        json.dumps(
            writable(candidate),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    try:
        deploy(args.id, payload_path)
    except Exception as e:
        print(f"FAIL: Homey update failed: {e}")
        return 2

    try:
        live_after = read_live(args.id)
    except Exception as e:
        print(f"FAIL: post-deploy read failed: {e}")
        print("WARNING: deployment state requires manual verification")
        return 3

    after_hash = sha256(writable(live_after))

    print("after hash:", after_hash)

    if after_hash == candidate_hash:
        backup(live_after, "verified")
        print("PASS: deploy verified by exact read-back hash")
        return 0

    print("FAIL: read-back does not match candidate")
    print("ROLLBACK: attempting predeploy restore")

    try:
        rollback_payload = pre_backup.with_suffix(pre_backup.suffix + ".payload")
        rollback_payload.write_text(
            json.dumps(
                writable(live_before),
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

        deploy(args.id, rollback_payload)
        rolled_back = read_live(args.id)
    except Exception as e:
        print(f"CRITICAL: rollback attempt failed: {e}")
        return 4

    rollback_hash = sha256(writable(rolled_back))

    if rollback_hash == before_hash:
        print("PASS: rollback verified")
        return 5

    print("CRITICAL: rollback read-back mismatch")
    return 6


if __name__ == "__main__":
    sys.exit(main())
