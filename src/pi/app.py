from __future__ import annotations

import asyncio

from config import Settings
from ems.state import CentralState
from health import HealthState


async def main() -> None:
    settings = Settings()
    settings.assert_safe_mode()

    state = CentralState()
    health = HealthState()
    health.mark_started()

    print(
        'Pi EMS bootstrap started '
        f'mode={settings.ems_mode.upper()} '
        f'schema={state.snapshot().schema_version} '
        f'homey={health.homey_status}'
    )

    try:
        while True:
            # Bootstrap heartbeat only. Homey reads remain intentionally disabled.
            # Use MockHomeyGateway for deterministic development until the exact
            # production read contracts are complete and Homey is safe to probe.
            await asyncio.sleep(60)
    finally:
        health.mark_stopped()


if __name__ == '__main__':
    asyncio.run(main())
