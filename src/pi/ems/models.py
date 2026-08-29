from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Quality(StrEnum):
    GOOD = "GOOD"
    STALE = "STALE"
    MISSING = "MISSING"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


class Observation(BaseModel, Generic[T]):
    value: T | None = None
    observed_at: datetime | None = None
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str
    quality: Quality = Quality.UNKNOWN
    stale_after_s: int | None = None

    def effective_quality(self, now: datetime | None = None) -> Quality:
        if self.quality is not Quality.GOOD:
            return self.quality
        if self.observed_at is None or self.stale_after_s is None:
            return self.quality
        now = now or datetime.now(timezone.utc)
        age_s = (now - self.observed_at).total_seconds()
        return Quality.STALE if age_s > self.stale_after_s else Quality.GOOD

    @property
    def usable(self) -> bool:
        return self.value is not None and self.effective_quality() is Quality.GOOD


class GridState(BaseModel):
    power_W: Observation[float] | None = None
    phase_power_W: list[Observation[float]] = Field(default_factory=list)
    phase_current_A: list[Observation[float]] = Field(default_factory=list)


class PvState(BaseModel):
    solaredge_W: Observation[float] | None = None
    goodwe4200_W: Observation[float] | None = None
    goodwe2000_W: Observation[float] | None = None

    def valid_total_W(self) -> float | None:
        values = [self.solaredge_W, self.goodwe4200_W, self.goodwe2000_W]
        if not all(v is not None and v.usable for v in values):
            return None
        return sum(float(v.value) for v in values if v is not None and v.value is not None)


class EvState(BaseModel):
    power_W: Observation[float] | None = None
    state: Observation[str] | None = None
    charger_available: Observation[bool] | None = None
    deadline_active: Observation[bool] | None = None


class WarmWaterState(BaseModel):
    boiler_power_W: Observation[float] | None = None
    boiler_on: Observation[bool] | None = None
    observer_state: Observation[str] | None = None
    goal_reached_today: Observation[bool] | None = None


class PowerIntent(BaseModel):
    ev_target_W: float = 0
    ww_target_W: float = 0
    source_revision: int = 0


class EmsState(BaseModel):
    schema_version: str = "PI_EMS_STATE_V0.1"
    revision: int = 0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    grid: GridState = Field(default_factory=GridState)
    pv: PvState = Field(default_factory=PvState)
    ev: EvState = Field(default_factory=EvState)
    ww: WarmWaterState = Field(default_factory=WarmWaterState)
    power_intent: PowerIntent = Field(default_factory=PowerIntent)
    degraded_reasons: list[str] = Field(default_factory=list)
