#!/usr/bin/env python3
"""Risk guard: retired WW shadow advice cannot turn into a boiler command."""

from pathlib import Path

core = Path("src/homey/core/core-v0.11p.candidate-homey.js").read_text(encoding="utf-8")

# No active Logic dependency on the retired 15-minute SHADOW producer.
assert "EM2_WW_PostGoal_Opportunity" not in core
assert "postGoalEligible" not in core
assert "postGoalFresh" not in core
assert "POST_GOAL_VALIDATED_SHOULD" not in core

# The existing source-mode and 19:00 hard stops remain ahead of the
# goal-reached branch; a completed day can never be reopened by Core.
mode = core.index("if(!mode){wwAction=")
deadline = core.index("else if(minuteOfDay>=1140){")
goal = core.index("else if(goalReachedToday){")
catchup = core.index("else if(catchupRequired){")
assert mode < deadline < goal < catchup
completed_day = core[goal:catchup]
assert "BOILER_ON" not in completed_day
assert "wwAction=boilerOn?'BOILER_OFF':'HOLD'" in completed_day
assert "wwPriority=boilerOn?'MUST':'MAY'" in completed_day
assert "postGoalPolicy:'DISABLED'" in core
assert "sameDayReheat:false" in core

# After-goal deactivation must not remove ordinary deadline/catch-up logic.
assert "wwOpportunity='CATCHUP'" in core
assert "THERMOSTAT_VERIFY" in core
assert "plannerGridAllowed" in core
print("PASS: WW post-goal SHADOW is retired; comfort/deadline guards retained")
