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
        "--output",
        type=Path,
        help="Atomically write the latest EMS oven state to this JSON file.",
    )
    return parser.parse_args()


def credentials():
    username = os.environ.get("CONNECTLIFE_USERNAME")
    password = os.environ.get("CONNECTLIFE_PASSWORD")

    if not username:
        username = input("ConnectLife e-mail: ").strip()

    if not password:
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

    while True:
        try:
            await poll_once(api, args.output)
        except Exception as exc:
            # Keep the last valid output file intact; a later integration layer can
            # mark it stale based on generatedAt instead of consuming partial JSON.
            print(f"ConnectLife poll mislukt: {exc}", file=sys.stderr, flush=True)

        await asyncio.sleep(args.interval)


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(run()))
    except KeyboardInterrupt:
        raise SystemExit(0)
