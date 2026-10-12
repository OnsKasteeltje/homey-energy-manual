# Heating Pi -> Homey six-room SHADOW V0.2

**Status: DRAFT / NO INSTALL / NO DEPLOY (2026-10-12).** Independent source contract; the proven but parked V0.1 Homey chain is untouched.

## Architecture

The existing Pi Heating V0.3 and V0.5 already expose six rooms. This versioned handoff has three new, separate source components:

1. Pi-only JSON builder: services/pi/integrations/homey/egress/build_heating_control_intent_six_room_shadow_v0_2.py
2. Uninstalled Homey Adapter: src/homey/adapters/heating-control/heating-control-v0.2.six-room.shadow.js
3. Uninstalled Homey Gate: src/homey/validation/heating-control-adapter-gate-v0.2.six-room.shadow.js

The builder reads ONLY local Heating V0.5 and independent READ_ONLY Honeywell vendor state. Output is JSON to stdout, schema EMS_HEATING_CONTROL_INTENT_V0.2. **There is no publisher, no Homey commissioning installer, no systemd unit or timer, and no second planner.** The Homey scripts are not installed. If a future separately approved SHADOW-only environment runs them, they may update only their dedicated Logic outputs and perform targeted thermostat reads for non-HOLD commands; never device writes.

Pinned six-room mapping:
- woonkamer: 6a79bb86-8c02-43db-be22-6f51e01efc6d
- eetkamer: dd7ef4a3-ed9f-4e4d-92bb-090502068421
- keuken: b7aec05b-953f-41e1-a7b4-ad09c9bf911e
- serre: 13625cb2-8fb5-4466-a21f-7addd8d72a88
- douwe_slaapkamer: f74252a1-2879-4967-ba2d-41f56364e39b
- erker_douwe: f9db36cd-8c0f-4beb-aa28-0127597652cf

## Guards / no physical authority

Exactly six non-duplicate room keys, exactly these device IDs, current Pi V0.5/read-only Honeywell snapshots, valid SHADOW freshness/order and no-write flags are required. Missing or corrupt sources fail closed with zero commands.

For ANY zone in permanent_override or temporary_override, the Pi builder forces a HOLD with target null, wouldWrite false, holdReason HONEYWELL_OVERRIDE_ACTIVE and no simulated ownership even if V0.5 suggests SET/KEEP/RESET. An unknown zone mode, a non-Auto Honeywell system mode, contradictory override end-time or changed target also results in HOLD. A simulated SET/KEEP also requires an upcoming scheduled UP transition. HOLD requires neither a future UP time nor an edge device read. Both new Homey components independently guard the six-ID mapping, the override HOLD rule, freshness and fail-closed semantics.

The fields wouldWrite / sourceShadowAction describe hypothetical, legacy V0.5 SHADOW semantics, never an actuator permit. All V0.2 contracts retain physicalWrite=false, deviceWrites=false, physicalWriteAllowed=false, liveExecutionAllowed=false, physicalOwnershipProven=false, plannerAuthority=SHADOW_ONLY and executor=HOMEY_SHADOW. No readback in this phase proves a physical override, actuator ACK or ownership.

**The original V0.1 Logic IDs, adapter/gate/commissioning scripts, publisher and disabled timer are unchanged; do NOT repoint or enable them.**

## Safe standalone Pi test

Run ONLY in an isolated worktree. This uses Python unittest-style asserts and Node test mocks, never Homey.

    set -euo pipefail
    cd /home/jeroen/ems/repo/homey-energy-manual
    git fetch origin feat/heating-homey-six-room-shadow-v0-2
    WT="/tmp/ems-heating-six-shadow-$(date +%s)"
    git worktree add --detach "$WT" FETCH_HEAD
    trap 'git worktree remove --force "$WT" >/dev/null 2>&1 || true' EXIT

    python3 -B "$WT/tests/integrations/test_heating_homey_six_room_shadow_v0_2.py"
    (
      cd "$WT"
      node --test tests/homey/heating-control-six-room-shadow-v0.2.test.mjs
    )

Optional local runtime evidence (no writes or publisher):

    python3 -B "$WT/services/pi/integrations/homey/egress/build_heating_control_intent_six_room_shadow_v0_2.py" |
    python3 -c '
    import json, sys
    d=json.load(sys.stdin)
    assert d["physicalWriteAllowed"] is False
    assert d["liveExecutionAllowed"] is False
    assert d["deviceWrites"] is False
    if d["valid"]:
        assert len(d["commands"])==6
        for c in d["commands"]:
            assert c["physicalWrite"] is False
            if c["roomKey"] in ("douwe_slaapkamer","erker_douwe") and c["vendorSetpointMode"] in ("permanent_override","temporary_override"):
                assert c["action"]=="HOLD"
        print("PASS: six-room local SHADOW contract")
    else:
        assert d["commands"]==[]
        print("SAFE FAIL_CLOSED:",d["reason"])
    '

A FAIL_CLOSED result may mean the independent V0.5 and Honeywell polling times do not overlap within their freshness windows. Never invent timestamps or relax controls to force success.

## Release boundary

This draft contains only an independent, versioned source implementation and offline tests. A future separately approved SHADOW commissioning PR is necessary before any Homey Logic/Flow installation. Nothing here authorizes a Honeywell physical write, automatic Pi publisher, old V0.1 restart, or LIVE canary. Full physical requirements remain in design PR #243.