# EMS production control process logic

Status: live production baseline 2026-09-13.

This document complements the component-chain architecture. It shows the actual decision logic implemented across Pi planning and Homey execution/safety. The diagrams intentionally use decision diamonds and explicit fail/HOLD/NOOP paths rather than only listing components.

## EV / Tesla control logic

```mermaid
flowchart TD
    A[Read EM2_Planner_Authority and Pi /control/current] --> B{Authority = PI and command schema/owner/contract/freshness valid?}
    B -- no --> X[Fail closed / no valid positive intent]
    B -- yes --> C[Start with exact Pi EV slot target]

    C --> D{Realtime envelope V0.3 allowed and mode = PV_OPPORTUNITY?}
    D -- no --> E[Keep exact Pi slot target]
    D -- yes --> F{P1 and Easee live inputs valid?}
    F -- no --> E
    F -- yes --> G{Tesla connected?}
    G -- no --> H[Realtime target = 0 A]
    G -- yes --> I[Counterfactual surplus = max 0, -P1_W + EV_actual_W]
    I --> J[rawA = floor surplus / 690]
    J --> K{rawA >= 6 A?}
    K -- no --> H
    K -- yes --> L[Candidate = clamp 6..maxA inside Pi envelope]

    E --> M{Deadline guard required now?}
    H --> M
    L --> M
    M -- no --> N[Preserve current Pi/realtime target]
    M -- yes --> O[Override target = deadlineMaxA x 690 W]
    N --> P[Write EM2_Power_Intent v0.2]
    O --> P

    P --> Q{EV Adapter: schema/revision/freshness valid?}
    Q -- no --> R[Adapter invalid / requested_A 0]
    Q -- yes --> S{target_W = 0?}
    S -- yes --> T[requested_A = 0]
    S -- no --> U{target_W >= 6 x 690 W and charger state trusted?}
    U -- no --> T
    U -- yes --> V[requested_A = floor target_W / 690, clamp to policy max]

    R --> W{EV Gate exact mapping/revisions/safety PASS?}
    T --> W
    V --> W
    W -- no --> Y[Gate FAIL]
    W -- yes --> Z{Actuator LIVE + fresh + gate revisions aligned?}
    Z -- no --> AA[Physical fail-closed target 0 A]
    Z -- yes --> AB{requested_A = 0?}
    AB -- yes --> AC[Normalize Easee target current to 0 A]
    AB -- no --> AD{Easee session state?}
    AD -- paused --> AE[Resume; if still paused after delay then Start]
    AD -- plugged_in --> AF[Start charging]
    AD -- charging --> AG[Continue]
    AE --> AH[Revalidate adapter/gate and reassert requested current]
    AF --> AH
    AG --> AH
```

### EV decision details

- The realtime opportunity controller is bounded by the Pi envelope; Homey is not a second planner.
- Counterfactual surplus is `max(0, -P1_W + EV_actual_W)` because P1 is net after the currently charging EV.
- START6/RUN6 mapping uses 690 W/A for 3 x 230 V and floors the upstream watt target to current.
- The executor-side deadline guard runs after realtime opportunity logic and can override it when the deadline becomes required.
- EV Device Health is observability-only; schema/revision/electrical mapping/freshness checks remain hard.
- The EV actuator is the sole automatic physical Easee writer and performs fail-closed zero-current normalization.

## WW / boiler planning logic

Source of planning logic: `src/pi/ems-runtime/planner/warm-water/build_ww_plan.py`.

```mermaid
flowchart TD
    A[Build daily WW plan before 19:00] --> B{Today and goalReachedToday?}
    B -- yes --> C[No required WW slots / HOLD]
    B -- no --> D[Determine required WW energy and 15-min slots]
    D --> E[Find contiguous positive-export PV windows]
    E --> F{Window meets minimum run and PV energy?}
    F -- no --> G[Ignore window]
    F -- yes --> H{Tesla connected now?}
    H -- no --> I[Choose strongest consecutive WW subrun]
    H -- yes --> J[Use PV-window shoulders to preserve central peak for Tesla]
    I --> K[Reserve selected PV slots]
    J --> K
    G --> L{All required slots allocated?}
    K --> L
    L -- yes --> M[Final WW plan]
    L -- no --> N{Catchup required OR insufficient unchosen slots >=16:00?}
    N -- no --> O[Fallback pool = unchosen slots from 16:00; choose latest first]
    N -- yes --> P[Fallback pool = all unchosen slots; allow earlier safety fallback]
    O --> M
    P --> M
```

Planning constants in the current source include a 1.9 kW boiler, hard 19:00 deadline, normal fallback from 16:00, minimum run of two 15-minute slots, and WW comfort reserved before EV opportunity.

## WW / boiler execution logic

```mermaid
flowchart TD
    A[EM2_Power_Intent targets.ww.target_on changed] --> B{Adapter input schema valid, intent valid, sourceRevision present?}
    B -- no --> C[WW Adapter INVALID]
    B -- yes --> D{target_on value}
    D -- true --> E[Adapter command onoff=true / OK_ON]
    D -- false --> F[Adapter command onoff=false / OK_OFF]
    D -- null --> G[Adapter command value=null / OK_HOLD]

    C --> H{WW Gate: exact schemas, revision alignment, adapter safety and mapping?}
    E --> H
    F --> H
    G --> H
    H -- no --> I[Gate FAIL; command=null]
    H -- yes --> J{Actuator LIVE armed?}
    J -- no --> K[BLOCKED_KILL_SWITCH; no physical write]
    J -- yes --> L{WW_Boilermodus = true?}
    L -- no --> M[BLOCKED_SOURCE_CV; no physical write]
    L -- yes --> N{Intent/adapter/gate schemas and source revisions aligned?}
    N -- no --> O[BLOCKED_GATE; no physical write]
    N -- yes --> P{Intent and gate age <= 10 minutes?}
    P -- no --> Q[BLOCKED_STALE; no physical write]
    P -- yes --> R{Command value}
    R -- null --> S[HOLD; no device read/write]
    R -- non-boolean --> T[BLOCKED_COMMAND]
    R -- boolean --> U[Read boiler by exact device ID]
    U --> V{Boiler onoff available?}
    V -- no --> W[BLOCKED_BOILER_READ/MISSING/ONOFF]
    V -- yes --> X{Current onoff already equals target?}
    X -- yes --> Y[NOOP_ALREADY_TARGET]
    X -- no --> Z[setCapabilityValue onoff once]
    Z --> AA[WRITE_OK]
```

## Production invariants

- Planner != device writer.
- Power Intent != device writer.
- Adapter != device writer.
- Gate != device writer.
- Exactly one actuator per domain performs automatic physical writes.
- Invalid or stale control data fails closed.
- Current contract mode is FIXED / `ENGIE_3Y_2026_2029`; dynamic-price data may not silently change production control mode.
