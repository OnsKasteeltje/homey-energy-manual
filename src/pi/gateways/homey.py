from __future__ import annotations

from dataclasses import dataclass

import httpx


DEVICE_IDS = {
    "p1": "7a696d77-15fb-4b68-9bce-f1e39bff5045",
    "easee": "65ee9fda-9535-44ab-8037-809587bc8f1c",
    "equalizer": "7dd35f8f-1dca-42f5-9b41-9b69bd14c611",
    "boiler": "8238b270-21a2-4284-aa78-6b9b58d254ab",
    "quatt": "1e5dcde5-c1cf-4c32-9141-33e00ce36de9",
    "solaredge": "c52c1c1d-9080-4a3b-b2e0-acc1eed7bf20",
    "goodwe4200": "9f55af14-a080-4129-8887-c81b95f649bb",
    "goodwe2000": "cbb98288-1c44-4718-9a66-13709b9d0172",
    "washer": "921c9604-b06e-43df-b903-2294a971c525",
    "dryer": "dfce2ff9-3d90-4721-9865-2a7bcc6d7100",
}


class HomeyRateLimited(RuntimeError):
    pass


@dataclass(frozen=True)
class HomeyGatewayConfig:
    base_url: str
    token: str
    timeout_s: float = 5.0


class HomeyGateway:
    """Only module allowed to perform Homey HTTP I/O.

    v0.1 deliberately provides reads only. No actuator write method exists yet.
    """

    def __init__(self, config: HomeyGatewayConfig) -> None:
        self._client = httpx.AsyncClient(
            base_url=config.base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {config.token}"},
            timeout=config.timeout_s,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_device(self, role: str) -> dict:
        device_id = DEVICE_IDS[role]
        response = await self._client.get(f"/api/manager/devices/device/{device_id}")
        if response.status_code == 429:
            raise HomeyRateLimited("Homey returned 429; no immediate retry permitted")
        response.raise_for_status()
        return response.json()
