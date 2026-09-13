#!/usr/bin/env python3

import argparse
import base64
import copy
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OWNER = "OnsKasteeltje"
REPO = "homey-energy-manual"
BRANCH = "main"
TARGET = "docs/data/energy-state-v2.json"
SOURCE = Path("/home/jeroen/ems/data/energy-state-v2.json")
TOKEN_FILE = Path("/home/jeroen/ems/secrets/github-planner-token")

EXPECTED_SCHEMA_VERSION = "2.12"
EXPECTED_SOURCE_PUBLISHER_PREFIX = "EM2_CORE_STATE_"
PUBLIC_PUBLISHER_VERSION = "EM2_PUBLISHER_V1.1.0"
MAX_SOURCE_SAMPLE_AGE_SECONDS = 20 * 60


def parse_ts(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise SystemExit(f"FAIL: {label} missing")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise SystemExit(f"FAIL: invalid {label}: {value!r}") from exc
    if dt.tzinfo is None:
        raise SystemExit(f"FAIL: {label} must be timezone-aware")
    return dt.astimezone(timezone.utc)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def load_source() -> dict:
    if not SOURCE.exists():
        raise SystemExit(f"FAIL: source missing: {SOURCE}")

    try:
        payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"FAIL: invalid source JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise SystemExit("FAIL: source must be a JSON object")

    for key in ("meta", "grid", "tesla", "hot_water"):
        if not isinstance(payload.get(key), dict):
            raise SystemExit(f"FAIL: required object missing: {key}")

    meta = payload["meta"]
    if meta.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise SystemExit(
            f"FAIL: schema mismatch: {meta.get('schema_version')!r} != {EXPECTED_SCHEMA_VERSION!r}"
        )

    source_publisher = meta.get("publisher_version")
    if not isinstance(source_publisher, str) or not source_publisher.startswith(EXPECTED_SOURCE_PUBLISHER_PREFIX):
        raise SystemExit(f"FAIL: unexpected source publisher: {source_publisher!r}")

    revision = meta.get("state_revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise SystemExit(f"FAIL: invalid state_revision: {revision!r}")

    sample_at = parse_ts(meta.get("source_sample_at"), "source_sample_at")
    age = (datetime.now(timezone.utc) - sample_at).total_seconds()
    if age < -60:
        raise SystemExit(f"FAIL: source_sample_at is in the future: age={age:.1f}s")
    if age > MAX_SOURCE_SAMPLE_AGE_SECONDS:
        raise SystemExit(
            f"FAIL: stale source_sample_at: age={age:.1f}s max={MAX_SOURCE_SAMPLE_AGE_SECONDS}s"
        )

    return payload


def build_public_payload(source: dict) -> dict:
    payload = copy.deepcopy(source)
    meta = payload["meta"]
    source_publisher = meta.get("publisher_version")
    now = iso_now()

    meta["publisher_version"] = PUBLIC_PUBLISHER_VERSION
    meta["generated_at"] = now
    meta["heartbeat_at"] = now
    meta["publish_reason"] = "PI_TELEMETRY"
    meta["source_publisher_version"] = source_publisher

    return payload


def github_request(token: str, method: str, url: str, body=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "EMS-Pi-Energy-State-Publisher",
    }
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        text = exc.read().decode(errors="replace")
        if exc.code == 404:
            return 404, None
        raise SystemExit(f"FAIL: GitHub HTTP {exc.code}: {text[:300]}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish Pi canonical energy state to GitHub telemetry")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and render publication metadata without contacting GitHub",
    )
    args = parser.parse_args()

    source = load_source()
    payload = build_public_payload(source)
    meta = payload["meta"]

    print("PASS: energy-state publication payload validated")
    print("source:", SOURCE)
    print("target:", TARGET)
    print("state_revision:", meta.get("state_revision"))
    print("source_sample_at:", meta.get("source_sample_at"))
    print("source_publisher_version:", meta.get("source_publisher_version"))
    print("publisher_version:", meta.get("publisher_version"))
    print("generated_at:", meta.get("generated_at"))

    if args.dry_run:
        print("DRY_RUN: no GitHub request performed")
        return

    if not TOKEN_FILE.exists():
        raise SystemExit(f"FAIL: token missing: {TOKEN_FILE}")
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        raise SystemExit("FAIL: token empty")

    content = base64.b64encode((json.dumps(payload, indent=2) + "\n").encode()).decode()
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{TARGET}"

    status, current = github_request(token, "GET", f"{url}?ref={BRANCH}")
    sha = current.get("sha") if status == 200 and current else None

    body = {
        "message": "chore: publish Pi energy state telemetry",
        "content": content,
        "branch": BRANCH,
    }
    if sha:
        body["sha"] = sha

    status, result = github_request(token, "PUT", url, body)
    if status not in (200, 201):
        raise SystemExit(f"FAIL: unexpected GitHub status {status}")

    print("PASS: Pi energy state telemetry published")
    print("commit:", result.get("commit", {}).get("sha"))


if __name__ == "__main__":
    main()
