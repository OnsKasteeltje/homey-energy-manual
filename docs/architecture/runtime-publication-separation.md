# Runtime publication separation

**Status:** Canonical target architecture / migration plan  
**Date:** 18 September 2026  
**Scope:** GitHub runtime publishers, website observability data and separation of canonical source from operational data  
**Governance:** `ems-architecture-governance.md`, `ems-software-architecture-live.md`, `architectuur-guardrails.md`

## 1. Decision

GitHub `main` is the canonical source for EMS software, configuration, schemas, tests and documentation. It is **not** an operational state transport, telemetry store, time-series database or command bus.

Runtime state, planner snapshots, history and observability required by the website must ultimately be exposed through a dedicated read-only operational data interface. The website consumes that interface without making the Git repository part of the live EMS chain.

This extends the existing rule that GitHub is not part of realtime control:

```text
Homey -> Pi runtime -> planning/control -> Homey       # operational/control
                  |
                  +-> read-only web data API -> website # presentation

GitHub main -> software/config/schemas/docs/tests       # canonical source
```

Failure of website publication must never affect state ingest, planning, safety, execution or physical devices.

## 2. Evidence: automatic mutations of main

Repository history on 18 September 2026 proves multiple automatic runtime publications to `main`.

| Publisher / commit family | Current artifact on main | Observed cadence | Meaning | Control role |
|---|---|---:|---|---|
| Pi energy-state telemetry | `docs/data/energy-state-v2.json` | 15 min | canonical Pi state transformed for website publication | observability only |
| rolling Planner Shadow publisher | `docs/data/energy-planner-shadow.json` | ~1 min | rolling Homey/shadow plan snapshot | observability only |
| Dynamic Pi Planner shadow publisher | `docs/data/energy-planner-shadow-dynamic.json` | observed ~15 min | Pi dynamic planner/forecast snapshot | PURE_SHADOW / none |
| Pi Planner shadow publisher | `docs/data/energy-planner-shadow-pi.json` | observed | Pi planner snapshot | observability/shadow |
| EV control-status publisher | `docs/data/ev-control-status.json` | multiple writes/min observed | EV execution/status observability | none |
| day-series publication | `docs/data/energy-day-v2.json` | observed 30 min | current-day history series | history/presentation |

The inventory is evidence-based, but not yet a claim that this is the complete set of all Pi/Homey timers. Live Pi systemd/Homey configuration must be cross-checked before retirement of any publisher.

## 3. Current website consumers

The current website has explicit dependencies on repository runtime artifacts:

| Website function | Current source |
|---|---|
| Live energy view | `docs/data/energy-state-v2.json` |
| Planner | raw GitHub `docs/data/energy-planner-shadow-dynamic.json` |
| Energy history — current day | `docs/data/energy-day-v2.json` |
| Energy history — compact archive | `docs/data/energy-daily-history.json` |
| Energy history — full-resolution 7-day archive | `docs/data/energy-day-series-7d.json` |
| EV status / diagnostics | `docs/data/ev-control-status.json` where consumed by legacy frontend |

The Pages workflow currently triggers on these runtime JSON paths. Runtime publication therefore causes source-branch mutations and potentially site rebuild/deploy activity. This is transitional technical debt, not the target architecture.

## 4. Canonical operational sources

The migration must preserve existing source-of-truth boundaries:

- current operational state: Pi runtime state produced from accepted Homey Core pushes;
- measurement history: `/home/jeroen/ems/data/ems-history.sqlite`;
- planner decision/replay history: `/home/jeroen/ems/data/planner-history.sqlite`;
- current validated planner/control output: Pi runtime endpoints/files;
- GitHub: software/configuration/contracts/documentation only.

JSON may remain as local derived/cache/API serialization, but must not require a Git commit to become visible to the website.

## 5. Target web-data boundary

The target is a read-only web data API owned by the Pi publication/integration boundary, separate from the control API in responsibility and failure behaviour.

Minimum conceptual resources:

```text
GET /web/state/current
GET /web/planner/current
GET /web/history/day?date=YYYY-MM-DD
GET /web/history/daily?from=...&to=...
GET /web/status/ev
```

Exact endpoint names and schemas are implementation decisions and must be versioned before cutover.

Requirements:

1. read-only for presentation resources;
2. schema-versioned;
3. freshness/generated/source timestamps retained;
4. no physical writes and no optimizer policy in the web layer;
5. API outage cannot block control;
6. browser access is explicitly secured and scoped;
7. history is read from canonical Pi history, not reconstructed from Git commits;
8. the new clean-room frontend consumes the API directly.

User commands (Tesla deadline, WW source, contract/settings) use a separate authenticated command interface. They are not implemented as Git commits and are not mixed into the read-only observability API.

## 6. Migration rule: no blind shutdown

Every artifact migrates independently:

```text
inventory
 -> implement equivalent Pi read-only resource
 -> parallel/dual publication
 -> compare schema + values + freshness + timestamps
 -> switch website consumer
 -> runtime/website validation
 -> stop main mutation for that artifact
 -> monitor
 -> retire obsolete GitHub artifact only after rollback window
```

A `runtime-data` Git branch may be used only as a short-lived migration fallback if needed. It is not the target architecture because Git remains an unsuitable operational telemetry/time-series transport.

No force-push is permitted. Existing history is left intact.

## 7. Migration matrix and retirement conditions

| Artifact | Target resource class | Main-write retirement condition |
|---|---|---|
| `energy-state-v2.json` | current-state API | Live consumer uses API; parity/freshness PASS; stale/API failure UI PASS |
| `energy-planner-shadow-dynamic.json` | planner-current API | Planner consumer uses API; 96-slot/schema/timezone parity PASS |
| `energy-planner-shadow-pi.json` | planner diagnostics API or retire if duplicate | consumer inventory proves requirement; equivalent available or consumer removed |
| `energy-planner-shadow.json` | legacy planner diagnostics API or retire | all consumers identified and migrated/retired |
| `ev-control-status.json` | EV status API | status/diagnostic consumers migrated; no control dependency confirmed |
| `energy-day-v2.json` | day-history API | current-day graph/KPIs parity PASS |
| `energy-daily-history.json` | daily-history API | historical day/week/month/year views use canonical history API |
| `energy-day-series-7d.json` | bounded history API | full-resolution history consumer migrated and recovery semantics validated |

## 8. Website design alignment

The clean-room frontend follows the same separation used by mature energy dashboards conceptually: current flows, historical series and control/input are distinct concerns.

For this EMS:

- **Live** consumes current operational state;
- **Planner** consumes planner output;
- **Energiehistorie** consumes canonical historical/statistical data;
- **Invoer** sends explicit authenticated commands/settings;
- GitHub serves/version-controls frontend and EMS source, not changing household state.

This preserves Tesla-like current-flow simplicity, Victron-like operational observability and Home-Assistant-like separation of current state from historical/statistical data without importing their implementation details.

## 9. Validation / Definition of Done

The architecture migration is complete only when:

```text
IMPLEMENTATION PASS
RUNTIME VALIDATION PASS
GITHUB SOURCE SYNC PASS
ARCHITECTURE DOCUMENTATION PASS
```

Additional acceptance criteria:

- normal runtime operation produces no telemetry/history/planner commits on `main`;
- `main` changes only through deliberate source/config/schema/docs changes and controlled automation for canonical source maintenance;
- website Live/Planner/History functionality remains available;
- Homey -> Pi and Pi -> Homey realtime paths are unchanged by the publication migration;
- loss of GitHub does not affect runtime or website operational data once cutover is complete;
- loss of the web-data API does not affect runtime/control;
- no second state/planner/control owner is introduced.

## 10. Current status

**ARCHITECTURE DECISION: PASS**  
**PUBLISHER INVENTORY: PARTIAL / repository evidence PASS, live Pi/Homey cross-check still required**  
**IMPLEMENTATION: NOT STARTED**  
**RUNTIME CUTOVER: NOT STARTED**

No publisher is disabled by this architecture decision.

## 11. Completed prerequisite — planner state-source separation

On 18 September 2026 an active runtime divergence was found during the
publisher inventory: the warm-water planner and quarter-hour shadow-load
planner still consumed the GitHub working-tree publication artifact
`docs/data/energy-state-v2.json`.

That artifact is derived website/observability output and is not a canonical
runtime input. At discovery it was materially behind the accepted local Pi
state, so retaining this dependency could expose planner logic to stale Tesla
`connected` and `charging` state.

This dependency has been removed:

- warm-water planner input: `/home/jeroen/ems/data/energy-state-v2.json`;
- quarter-hour shadow-load planner input: `/home/jeroen/ems/data/energy-state-v2.json`;
- source correction: commit `666d921ec`;
- isolated 96-slot builder validation: PASS;
- deployed runtime is byte-identical to committed source: PASS;
- normal `ems-forecast-chain.service` run at 20:33 CEST: PASS;
- `build_ww_plan.py`: `0/SUCCESS`;
- `build_shadow_load_plan.py`: `0/SUCCESS`;
- downstream dynamic planner, archive and website-shadow generation: PASS.

The resulting boundary is:

    accepted Homey Core state
            |
            v
    /home/jeroen/ems/data/energy-state-v2.json
            |
            +--> warm-water planner
            +--> quarter-hour shadow-load planner
            +--> other Pi runtime consumers
            |
            +--> transitional website publisher
                       |
                       v
              GitHub docs/data/energy-state-v2.json
                       |
                       v
                  legacy website

Therefore `docs/data/energy-state-v2.json` is no longer an input to these
planner components. Its remaining publication must not be retired until the
website consumer has been migrated and the retirement conditions in section 7
have passed.

**PREREQUISITE STATE-SOURCE SEPARATION: PASS**
## 12. Mandatory Web Data API security baseline

All implementation and migration of the dedicated read-only operational-data interface MUST follow `docs/architecture/web-data-api-security.md`. That contract applies to the entire Frontend V2 data boundary, not only the first WW Seasonal Advice resource. Security validation is a release gate: no direct public Pi port, authenticated/authorized HTTPS access through the approved external boundary, strict read-only method/resource allowlists, minimal CORS, bounded queries, response-field minimization and failure isolation from control.

