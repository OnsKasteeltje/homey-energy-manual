from __future__ import annotations

import asyncio
import os

from ems.state import CentralState


async def main() -> None:
    mode = os.getenv("EMS_MODE", "SHADOW").upper()
    if mode != "SHADOW":
        raise RuntimeError("Pi EMS v0.1 is SHADOW-only; LIVE mode is not implemented")

    state = CentralState()
    print(f"Pi EMS bootstrap started mode={mode} schema={state.snapshot().schema_version}")

    while True:
        # Bootstrap heartbeat only. Homey reads are intentionally not started here yet.
        # The first reader will be added after its exact input contract is captured.
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
