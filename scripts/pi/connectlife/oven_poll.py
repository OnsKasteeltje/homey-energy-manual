#!/usr/bin/env python3

import asyncio
import getpass
import json
import os
import sys

from connectlife.api import ConnectLifeApi
from connectlife.appliance import DeviceType

from oven_state import build_state


async def main():
    username = os.environ.get("CONNECTLIFE_USERNAME")
    password = os.environ.get("CONNECTLIFE_PASSWORD")

    if not username:
        username = input("ConnectLife e-mail: ").strip()

    if not password:
        password = getpass.getpass("ConnectLife wachtwoord: ")

    if not username or not password:
        print("E-mail of wachtwoord ontbreekt.", file=sys.stderr)
        return 2

    api = ConnectLifeApi(username=username, password=password)
    await api.login()
    appliances = await api.get_appliances()

    oven = None
    for appliance in appliances:
        if appliance.device_type == DeviceType.OVEN:
            oven = appliance
            break

    if oven is None:
        print("Geen oven gevonden in ConnectLife-account.", file=sys.stderr)
        return 3

    print(json.dumps(build_state(oven), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
