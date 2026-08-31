from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MockHomeyGateway:
    devices: dict[str, dict[str, Any]] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    reads_total: int = 0

    async def read_device(self, device_id: str) -> dict[str, Any]:
        self.reads_total += 1
        if device_id not in self.devices:
            raise KeyError(f'Unknown mock device: {device_id}')
        return {
            **self.devices[device_id],
            '_mock_observed_at': datetime.now(timezone.utc).isoformat(),
        }

    async def read_variable(self, variable_id: str) -> Any:
        self.reads_total += 1
        if variable_id not in self.variables:
            raise KeyError(f'Unknown mock variable: {variable_id}')
        return self.variables[variable_id]

    async def write_device(self, *_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError('MockHomeyGateway: physical writes are forbidden in SHADOW')
