#!/usr/bin/env python3

import argparse
import asyncio
import getpass
import json
import os
import sys
from pathlib import Path

from connectlife.api import ConnectLifeApi
from connectlife.appliance import DeviceType

from oven_state import build_state


def parse_args():
    parser = argparse.ArgumentParser(
        description="Read the ConnectLife oven state using one persistent login session."
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Keep polling with the same authenticated API session.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Polling interval in seconds when --watch is used (default: 60).",
    )
    parser.add_argument(
        "--max-failures",
        type=int,
        default=3,
        help="Exit after this many consecutive failed polls so systemd can restart the service (default: 3).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Atomically write the latest EMS oven state to this JSON file.",
    )
    return parser.parse_args()


def credentials():
    username = os.environ.get("CONNECTLIFE_USERNAME")
    password = os.environ.get("CONNECTLIFE_PASSWORD")

    if not username:
        if not sys.stdin.isatty():
            raise ValueError("CONNECTLIFE_USERNAME ontbreekt in niet-interactieve modus.")
        username = input("ConnectLife e-mail: ").strip()

    if not password:
        if not sys.stdin.isatty():
            raise ValueError("CONNECTLIFE_PASSWORD ontbreekt in niet-interactieve modus.")
        password = getpass.getpass("ConnectLife wachtwoord: ")

    if not username or not password:
        raise ValueError("E-mail of wachtwoord ontbreekt.")

    return username, password


def find_oven(appliances):
    for appliance in appliances:
        if appliance.device_type == DeviceType.OVEN:
            return appliance
    return None


def write_atomic(path: Path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


async def poll_once(api, output=None):
    appliances = await api.get_appliances()
    oven = find_oven(appliances)

    if oven is None:
        raise RuntimeError("Geen oven gevonden in ConnectLife-account.")

    state = build_state(oven)

    if output:
        write_atomic(output, state)

    print(json.dumps(state, indent=2), flush=True)
    return state


async def run():
    args = parse_args()

    if args.interval < 60:
        print("Polling interval moet minimaal 60 seconden zijn.", file=sys.stderr)
        return 2

    if args.max_failures < 1:
        print("--max-failures moet minimaal 1 zijn.", file=sys.stderr)
        return 2

    try:
        username, password = credentials()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    api = ConnectLifeApi(username=username, password=password)

    # Authenticate once. In --watch mode the same API instance/session is reused
    # for every poll instead of logging in once per minute.
    await api.login()

    if not args.watch:
        await poll_once(api, args.output)
        return 0

    failures = 0

    while True:
        try:
            await poll_once(api, args.output)
            failures = 0
        except Exception as exc:
            failures += 1
            # Keep the last valid output file intact. Consumers determine staleness
            # from generatedAt; after repeated failures we exit so systemd performs
            # a clean restart/login instead of hammering the authentication endpoint.
            print(
                f"ConnectLife poll mislukt ({failures}/{args.max_failures}): {exc}",
                file=sys.stderr,
                flush=True,
            )
            if failures >= args.max_failures:
                return 4

        await asyncio.sleep(args.interval)


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(run()))
    except KeyboardInterrupt:
        raise SystemExit(0)
