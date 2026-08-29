from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock

from .models import EmsState, Observation, Quality


class CentralState:
    """Single in-process authoritative EMS state for bootstrap v0.1."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._state = EmsState()

    def snapshot(self) -> EmsState:
        with self._lock:
            state = deepcopy(self._state)
            state.generated_at = datetime.now(timezone.utc)
            return state

    def update_grid_power(self, observation: Observation[float]) -> None:
        with self._lock:
            self._state.grid.power_W = observation
            self._bump_revision()

    def replace(self, state: EmsState) -> None:
        with self._lock:
            self._state = deepcopy(state)
            self._bump_revision()

    def evaluate_safety(self) -> list[str]:
        """Return reasons that block positive flexible-load commands.

        Missing/stale safety inputs are never interpreted as valid zero values.
        """
        with self._lock:
            reasons: list[str] = []
            grid = self._state.grid.power_W
            if grid is None:
                reasons.append("GRID_POWER_MISSING")
            elif grid.effective_quality() is not Quality.GOOD or grid.value is None:
                reasons.append(f"GRID_POWER_{grid.effective_quality().value}")

            if self._state.power_intent.ev_target_W > 0:
                available = self._state.ev.charger_available
                if available is None or not available.usable or available.value is not True:
                    reasons.append("EV_AVAILABILITY_NOT_GOOD")

            self._state.degraded_reasons = reasons
            return list(reasons)

    def positive_writes_allowed(self) -> bool:
        return not self.evaluate_safety()

    def _bump_revision(self) -> None:
        self._state.revision += 1
        self._state.generated_at = datetime.now(timezone.utc)
