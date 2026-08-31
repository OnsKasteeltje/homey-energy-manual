from __future__ import annotations

import time
from dataclasses import dataclass, field

from prometheus_client import Counter, Gauge, Histogram

HOMEY_READS = Counter('homey_reads_total', 'Homey read operations')
HOMEY_READ_FAILURES = Counter('homey_read_failures_total', 'Failed Homey read operations')
HOMEY_429 = Counter('homey_429_total', 'Homey HTTP 429 responses')
HOMEY_LATENCY = Histogram('homey_read_latency_seconds', 'Homey read latency in seconds')
STATE_AGE = Gauge('state_age_seconds', 'Age of the oldest safety-relevant state value')
EMS_UP = Gauge('ems_up', 'Pi EMS process health')


@dataclass
class HealthState:
    started_monotonic: float = field(default_factory=time.monotonic)
    homey_status: str = 'NOT_STARTED'
    database_status: str = 'NOT_CHECKED'
    mqtt_status: str = 'NOT_CHECKED'
    degraded_reasons: list[str] = field(default_factory=list)

    def mark_started(self) -> None:
        EMS_UP.set(1)

    def mark_stopped(self) -> None:
        EMS_UP.set(0)

    def snapshot(self) -> dict[str, object]:
        return {
            'status': 'DEGRADED' if self.degraded_reasons else 'OK',
            'uptime_s': round(time.monotonic() - self.started_monotonic, 3),
            'homey': self.homey_status,
            'database': self.database_status,
            'mqtt': self.mqtt_status,
            'degraded_reasons': list(self.degraded_reasons),
        }
