# CURRENT EMS STATE

> **Canonical current-state document** for the Raspberry Pi / Homey EMS.
>
> This file describes the intended current operational architecture and logic. Architecture-sensitive runtime, planner, systemd, contract-policy and Homey/Pi responsibility changes must update this document in the same release range.

**Status date:** 2026-09-19  
**Verified against:** GitHub `main`, current Pi control architecture, 2026-09-13 Homey/Pi production validation, 2026-09-14 history-chain incident analysis, 2026-09-15 Honeywell read-only recovery/validation and Heating Preheat V0.2 shadow consolidation, 2026-09-17 energy-state website publication recovery, and 2026-09-18 WW BOILER→CV manual-source validation / seasonal-advisor cadence alignment, and 2026-09-19 Homey Core v0.11p schema 2.13 state-contract cutover  
**Repository:** `OnsKasteeltje/homey-energy-manual`  
**Primary runtime host:** Raspberry Pi `ems-pi`

Detailed bidirectional runtime chain: `docs/architecture/homey-pi-runtime-dataflow.md`.

Canonical diagnostic source-of-truth and mandatory root-cause documentation rule: `docs/architecture/diagnostic-source-of-truth.md`. End-to-end troubleshooting MUST first identify the canonical source at each boundary; when root cause is established, reusable chain knowledge MUST be captured there before the investigation is considered architecturally complete.

- The Tesla/EMS authenticated command Worker source is canonical under `apps/cloudflare/` (migrated from legacy top-level `cloudflare/` under the repository “touch it, place it correctly” rule). Its explicit browser-origin allowlist contains the transitional GitHub Pages origin and the private LAN V2 origin `http://192.168.1.42`; wildcard CORS is forbidden. Cloudflare Git build configuration must use root directory `/apps/cloudflare` and include/watch only `apps/cloudflare/**`, so generated `docs/data/*` runtime-publication commits cannot consume Worker build capacity.

## 1. Source of truth

- GitHub `main` is authoritative for Pi runtime source, deployment definitions and architecture documentation.
- Deployed runtime: `/home/jeroen/ems/runtime/`.
- Pi repository checkout: `/home/jeroen/ems/repo/homey-energy-manual`.
- SQLite `/home/jeroen/ems/data/ems-history.sqlite` is the canonical operational measurement history.
- SQLite `/home/jeroen/ems/data/planner-history.sqlite` is the canonical planner decision/replay history.
- JSON under `/home/jeroen/ems/data/` and `docs/data/` is derived state, cache or publication output.
- Homey Logic variable `EM2_Planner_Authority` is the sole runtime selector between Homey and Pi planner authority.
- GitHub is **not** a runtime transport dependency for live Homey ↔ Pi state or control.

Operational energy history follows the canonical Homey → Pi state direction. Accepted Core state pushes are archived locally on the Pi; automatic Pi polling of Homey Insights is not a production history transport.

### 1.1 Ruimteverwarming — Honeywell baseline, PV-voorverwarming and Thermal Learning

Honeywell/Resideo remains the comfort and schedule authority. The canonical vendor acquisition boundary is `services/pi/integrations/honeywell/`; it produces `EMS_HONEYWELL_SCHEDULE_V0.2` and `EMS_HONEYWELL_STATE_V0.2` without physical writes.

The canonical EMS interpretation layer is `services/pi/state/heating/build_heating_room_model.py`, schema `EMS_HEATING_ROOM_MODEL_V0.1`. It joins schedule and current room state by stable canonical room key, preserves the actual Honeywell target separately from the scheduled baseline, and classifies the next baseline transition as `UP`, `DOWN` or `NONE` using scheduled current/next targets only. EMS-facing schedule timestamps are offset-aware in `Europe/Amsterdam`.

The canonical shadow preheat layer is `services/pi/planner/heating/build_heating_preheat_plan.py`, schema `EMS_HEATING_PREHEAT_PLAN_V0.2`. It remains **READ_ONLY / SHADOW** and creates no physical writes. PV-preheat scope is explicitly limited to `woonkamer`, `eetkamer`, `keuken` and `serre`; `woonkamer` and `eetkamer` carry common `living_area` grouping metadata. Other Honeywell rooms remain normal baseline/comfort rooms but are outside PV-preheat scope.

Only an upcoming Honeywell `UP` transition can become a preheat candidate. The provisional maximum advancement horizon is 180 minutes. Measured room temperature is decisive: when the later Honeywell target is already satisfied, no preheat candidate exists. When an eligible larger baseline increase is advanced, V0.2 exposes candidate setpoint steps of at most 0.5 °C and skips already-satisfied steps. The later Honeywell target is an absolute ceiling. `DOWN` and `NONE` transitions are never advanced.

Normal Honeywell schedule execution remains baseline comfort demand. EMS creates no new heat demand. PV-voorverwarming may only shift already-planned future Honeywell demand earlier when usable forecast PV-export potential exists; it must not intentionally create grid import merely to absorb energy. `candidate.startAt` remains `null` in the heating-preheat layer. Forecast PV-export evaluation and eventual joint allocation with WW and EV remain the responsibility of the existing Dynamic Pi Planner; this release does **not** modify that planner.

No thermal power, heat-up duration, COP, building heat loss or room-response coefficient is invented by Heating Preheat V0.2. The 180-minute horizon and 0.5 °C advancement steps are shadow guardrails, not learned physical constants.

The former legacy `src/pi/ems-runtime/thermal/build_thermal_observer.py` is retired rather than migrated as a parallel thermal model. Its overlapping Honeywell/schedule/room-state responsibility is superseded by the canonical Heating Room Model. There must not be both `EMS_THERMAL_OBSERVER_V0.1` and `EMS_HEATING_ROOM_MODEL_V0.1` as competing descriptions of room-heating state.

Quatt acquisition that remains useful for thermal analysis is canonicalized under `services/pi/integrations/quatt/collect_quatt_current.py`. The production systemd unit points to this target-structure source. Quatt telemetry, canonical room state and historical measurements form the input basis for **Heating Thermal Learning**: empirical evaluation of room response, heat retention, useful advancement horizon and rebound around the original Honeywell comfort time. Thermal Learning is observational; it does not create a second comfort authority or physical writer.

Detailed component documentation is under `docs/software-architecture/components/space-heating.md`, `heating-room-model.md` and `heating-preheat-plan.md`.

Honeywell runtime deployment remains a mixed managed/runtime-state directory. Repository-managed source may be refreshed, but host-local `.venv/`, `config/account.env`, `cache/oauth-token.json` and last valid generated outputs must survive normal source deployment. Secrets, OAuth cache and generated runtime output remain outside GitHub.

## 2. Control architecture

There are two deliberately separate runtime directions.

### 2.1 State direction — Homey → Pi

```text
Homey devices / P1 / PV / Easee / boiler / Quatt
                    ↓
        Homey Core v0.11p
                    ↓
            EM2_Public_State
                    ↓
EM v2 | 05 Transport | Homey→Pi State Push v0.1
                    ↓
 POST /state/energy over trusted LAN
                    ↓
         ems-status-api.service
                    ↓
 state_ingest validation / anti-replay
             ↙                    ↘
 energy-state-v2.json        ems-history.sqlite
             ↓                    ↓
        Pi forecast / planner / analytics
```

The state path is push-based. The Pi must not poll Homey merely to reconstruct canonical Core state. Accepted state is written atomically to `/home/jeroen/ems/data/energy-state-v2.json`; accepted payloads are also archived locally to operational history. Freshness and ordering use source timestamps and monotonic revision semantics; stale, future-skewed, replayed or malformed payloads fail closed.

Homey Core v0.11p publishes state schema 2.13. Schema 2.13 adds cumulative counters `grid.energy_import_kwh`, `grid.energy_export_kwh`, `pv.solaredge_energy_kwh`, `pv.goodwe_4200_energy_kwh` and `pv.goodwe_2000_energy_kwh`. The Homey→Pi transport is intentionally not the semantic schema-compatibility owner: it requires a present schema identifier and valid publisher family but does not pin one exact schema version. Canonical Pi `services/pi/integrations/homey/ingress/state_ingest.py` owns compatibility and currently accepts the explicitly reviewed set `{2.12, 2.13}`; unknown versions remain fail-closed. Runtime validation on 2026-09-19 accepted a genuine v0.11p/schema-2.13 push with HTTP 202 and `stateWritten=true`, and the five cumulative counters were present in canonical `energy-state-v2.json`.

### 2.2 Control direction — Pi → Homey

```text
Pi forecasts + history + fixed-contract policy
                    ↓
        Pi hardened dynamic planner
                    ↓
          Pi /control/current
                    ↓
 Homey PI Dynamic Planner Bridge
                    ↓
          EM2_Power_Intent
             ↙             ↘
       EV chain          WW chain
 adapter → gate       adapter → gate
       ↓                  ↓
 EV actuator LIVE    WW actuator LIVE
       ↓                  ↓
     Easee              boiler
```

The Pi is the active planner authority. Homey is the realtime state, executor and local safety layer. The planner itself never writes physical devices. `EM2_Planner_Authority` remains the single HOMEY↔PI authority gate; dual planner authority or dual independent writers are forbidden.

### 2.3 Production website / operational-data boundary

The private Pi-hosted EMS frontend is the **production website**. Live operational data is served same-origin through Caddy and the dedicated read-only Web Data API. The canonical Live resource is `GET /web/state/current`, projected from `/home/jeroen/ems/data/energy-state-v2.json` through an explicit allowlist.

Production presentation path: private EMS frontend -> Caddy on trusted LAN -> `/web/*` -> Web Data API `127.0.0.1:3200` -> canonical Pi runtime state.

GitHub is not runtime-state transport for the production Live website. The former GitHub energy-state publisher `services/pi/integrations/github/publish_energy_state.py` and `ems-energy-state-publication.timer` are retired from production scheduling. The timer is disabled and inactive. `docs/data/energy-state-v2.json`, publisher source and deployment units are retained temporarily as rollback/retirement artifacts until repository cleanup.

The former MkDocs/GitHub Pages Live energy view is retired as the production Live frontend. Planner, History and Groups/Phases may remain temporarily available through the legacy site until equivalent production-frontend resources are migrated. This temporary legacy availability does not make GitHub an allowed production runtime-state boundary.

## 3. Production contract policy

Production remains locked to the fixed three-year ENGIE contract:

- `productionContractMode = FIXED`;
- `productionContractId = ENGIE_3Y_2026_2029`;
- `productionSupplier = ENGIE`;
- dynamic pricing is **disabled for production**;
- dynamic prices may only be used for shadow, analysis or replay;
- automatic fallback to DYNAMIC is forbidden;
- automatic contract-mode switching is forbidden;
- invalid or inconsistent configuration must fail closed.

Ordering rule:

**contract mode → permitted economic model → permitted price source → planner decision**

## 4. Pi planning chain

The active general planner remains the hardened rolling 24-hour Pi planner with 96 quarter-hour slots. It owns joint strategic allocation of flexible demand while preserving hard comfort/safety feasibility. The term **dynamic planner** refers to rolling optimization, not a dynamic electricity contract.

Heating Preheat V0.2 does not alter the active Dynamic Pi Planner. It exposes only validated shadow advancement candidates; PV-slot selection and any later competition/allocation between WW, heating-preheat and EV remain outside the heating candidate builder.

Planner decisions are archived best-effort in `/home/jeroen/ems/data/planner-history.sqlite`; measured actuals remain in `/home/jeroen/ems/data/ems-history.sqlite`. Retrospective performance analysis must distinguish measured actuals, archived decision context and any unconstrained upper-bound benchmark from a future constrained replay optimum.

## 5. Current control endpoint

The Pi exposes `GET /control/current`. A valid production response uses schema `EMS_PI_CONTROL_COMMAND_V0.1`, is bounded to the current quarter-hour slot and planner validity, and fails closed on stale or invalid planner input. The endpoint is a readiness/command endpoint, not a second authority selector.

## 6. Current state ingest and history endpoint

The Pi exposes `POST /state/energy` for authenticated Homey→Pi state ingestion. Missing/incorrect authentication, malformed state, stale state, replayed state and non-approved schema versions fail closed for current-state acceptance. Exact schema-version compatibility is owned here rather than in the transport layer; the current approved set is `{2.12, 2.13}`. Operational history insertion is idempotent; a local history-archive failure must not invalidate otherwise fresh accepted live state.

Legacy Homey Insights/day-history polling may remain only as explicit backfill/diagnostic tooling and must not run as an automatic production history transport.

For Energiehistorie V2, Homey Core schema 2.13 cumulative counters are archived as first-class observations in the same canonical `measurements` table: P1 `energy_import_kwh` / `energy_export_kwh` and per-inverter `energy_produced_kwh` for SolarEdge, GoodWe 4200 and GoodWe 2000. Period energy is derived from validated non-negative counter deltas; counter resets/replacements/rollovers must be surfaced as discontinuities rather than negative energy. Household consumption is derived as `grid import + PV production - grid export`. The three PV counters remain separate through the history contract so Frontend V2 can provide PV hover/detail per inverter as well as aggregate PV. Realtime control continues to use P1/inverter power and freshness; cumulative counters do not become a realtime control input.

Derived household history is owned by `services/pi/history/build_house_energy_history.py`. It creates `house_energy_intervals` from consecutive complete five-counter snapshots. Each interval retains P1 import/export and all three PV deltas separately, plus aggregate PV and `house_kwh = import_kwh + pv_total_kwh - export_kwh`. A counter decrease is stored as a discontinuity with null energy values, never as negative energy. Gap classification is source-resolution-aware: normal coarse backfill intervals are not mislabeled as missing data, while intervals materially larger than their source resolution remain numerically derivable but are explicitly quality-marked `gap`. Counter decreases larger than the defined floating-point tolerance remain discontinuities; insignificant counter rounding noise is not treated as a reset. Presentation/aggregation must surface reduced coverage rather than silently treating it as complete.

Historical cumulative counters may be seeded only through the explicit maintenance importer `tools/maintenance/homey/import_energy_counter_backfill.py`. The importer consumes a captured Homey Insights export; it has no Homey connection, service or timer and therefore does not create a production polling path. Imported observations are marked `quality=backfill` with their source resolution. Normal ongoing history remains exclusively push-fed through Homey Core -> Pi ingress.

Derived operational history is rebuilt locally from canonical `measurements` and is deliberately independent from live state ingest and control. `services/pi/history/build_15m_history.py` owns deterministic raw-to-quarter-hour aggregation into `measurements_15m`; `services/pi/history/build_daily_energy_history.py` owns raw-to-daily boiler energy aggregation into `daily_energy_history`. Production scheduling is owned by independent `ems-history-15m.timer` and `ems-history-daily.timer` units. `ems-history-15m.service` runs both the canonical 15-minute aggregation and `build_house_energy_history.py` at :02, :17, :32 and :47 each hour, so newly push-archived cumulative counters are continuously projected into `house_energy_intervals` without Homey polling or a second raw-history writer. Failure of either derived-history builder must remain observable but must not block Homey→Pi state ingest, planning, `/control/current` or Homey execution. These builders must not poll Homey or create an alternative raw-history writer. Runtime validation on 2026-09-19 at 23:02 CEST confirmed the timer-triggered production run completed both builders successfully and advanced canonical `house_energy_intervals` automatically to 1068 intervals, with the newest derived interval ending at 23:02 CEST and quality `observed`.

## 7. Tesla production chain

Tesla charging remains split between Pi planning and Homey guarded execution. Opportunity charging uses residual PV subject to executable Easee limits; explicit deadline charging is a hard requirement and may use grid energy when required. Homey may trim within the Pi envelope but must not become a second independent planner. The guarded EV actuator remains the sole automatic physical Easee writer in the production EV chain.

## 8. Warm-water production chain

WW comfort remains a hard constraint above optimization. The Pi schedules remaining required heating before the comfort deadline and prefers useful PV periods. Homey translates the Power Intent through the WW adapter/gate chain; the guarded Warm Water Actuator remains the physical boiler writer. Source mode, kill switch, freshness and current device state are checked before writes.

The Pi WW Seasonal Source Advisor is read-only and manual-switch-only. It runs daily at 00:05 Europe/Amsterdam against canonical Pi-local history, so the just-completed local calendar day is immediately eligible for `completeDaysOnly` analysis. It has no dependency on the retired `ems-day-history.service` or other Homey Insights polling; source-switch advice requires the configured multi-day confirmation before notification and never performs a physical source switch. Confirmation is counted once per unique analysis `asOfDate`; reruns, restarts and persistent-timer catch-up executions for the same analysis day are idempotent and must not advance the confirmation streak. On 2026-09-18 the manual BOILER→CV change was validated end-to-end: Homey `WW_Boilermodus=false` resolved to Pi `currentMode=CV`, the advisor retained `KEEP_CURRENT` because CV was economically preferable, and the prior switch-to-CV confirmation streak reset to 0 without any automatic source write.

## 9. Live cutover validation

The controlled 2026-09-12 cutover validated Pi→Homey→Tesla and Pi→Homey→boiler end-to-end. The Homey→Pi state direction was validated in production on 2026-09-13 using genuinely fresh Homey Core state. Synthetic freshness must not be used as production evidence.

The 2026-09-14 history incident demonstrated that a separate Homey Insights pull chain is unsuitable as the production history transport; accepted Homey state pushes are archived locally instead.

Heating Preheat V0.2 remains shadow-only. No Honeywell, Homey or Quatt physical control is introduced by this release, so no heating-control cutover is claimed.

The 2026-09-17 energy-state website incident was isolated to the GitHub observability publication path: canonical local Pi state remained fresh while `docs/data/energy-state-v2.json` stopped updating after 2026-09-14 20:03 local time. Restoring this publisher must not restore the retired Pi→Homey control-push timer.

## 10. Failure behavior

If Homey Core publication stops, local Pi state ages and planner freshness checks eventually fail closed. Freshness limits must not be relaxed merely to keep planning alive. History-only failures are observable but must not turn fresh live state or a valid planner output into a control-path outage.

If the Pi plan or `/control/current` becomes stale or invalid, the Homey PI bridge must reject production readiness and downstream adapter/gate/actuator logic remains fail closed. Loss of GitHub availability must not interrupt the live Homey↔Pi runtime transport.

Failure of `ems-energy-state-publication.service` affects website observability only. It must be visible as stale publication data but must not be treated as a runtime/control outage.

## 11. Runtime / repository discipline

Deployment pattern: **inspect → minimal change → update architecture → architecture gate → deploy → validate → monitor**.

GitHub `main` remains authoritative. Production `deploy/systemd/` must contain only units valid for the intended runtime architecture. New/touched code follows **touch it, place it correctly**.

Canonical heating placement is now:

```text
services/pi/integrations/honeywell/   # vendor schedule/state acquisition
services/pi/integrations/quatt/       # Quatt telemetry acquisition
services/pi/state/heating/             # canonical Heating Room Model / future thermal state learning
services/pi/planner/heating/           # READ_ONLY/SHADOW preheat candidate construction
```

Canonical warm-water planner placement is now:

```text
services/pi/planner/warm-water/        # WW planning + Seasonal Source Advisor
```

The production runtime path remains `/home/jeroen/ems/runtime/planner/warm-water/`. Repository placement and runtime placement are deliberately decoupled: deployment maps the target-structure source to this stable runtime path, and drift/integrity validation checks that mapping. The WW migration therefore changes repository ownership without changing systemd execution paths or runtime control ownership.

The former GitHub website energy-state publisher remains temporarily under `services/pi/integrations/github/` as a rollback/retirement artifact. It is not production-scheduled and must not be re-enabled as a production Live transport.

The target Frontend V2 operational-data boundary is the dedicated read-only EMS Web Data API under `services/pi/api/web-data/`. It is separate in responsibility and failure behaviour from the existing runtime/control status API. The Web Data API is presentation transport only: it has no EMS policy, optimizer, Homey/device write or actuator path. The initial resource is WW Seasonal Advice; the same boundary is intended to serve later Live, Planner, History and observability resources through explicitly versioned allowlisted contracts.

The Web Data API security baseline is mandatory and canonical in `docs/architecture/web-data-api-security.md`. The origin is private and binds locally by default. Frontend V2 is now explicitly targeted as a private Pi-hosted website: local browser access is limited to the trusted home LAN and remote access to authorized devices/users through the Tailscale tailnet. No router port-forward, public internet ingress, Tailscale Funnel or Cloudflare/public tunnel is part of the current target architecture. The preferred final browser/API path is same-origin through the Pi private web ingress while the API remains localhost-scoped. GitHub Pages is transitional during migration, not the target V2 runtime host. User command/write interfaces remain separate. Creating this foundation does not disable any existing GitHub runtime publication or change the live Homey↔Pi control path.

History V2 is repository-defined on the same read-only boundary through `GET /web/history/day/YYYY-MM-DD`, `/week/YYYY-MM-DD`, `/month/YYYY-MM` and `/year/YYYY` using schema `EMS_WEB_HISTORY_V1`. These resources query only canonical `house_energy_intervals`, use Europe/Amsterdam calendar boundaries, expose house/PV/import/export plus all three inverter contributions, and explicitly report coverage, gaps and discontinuities. Day series are hourly, week/month series daily and year series monthly; coarse source intervals are apportioned across presentation buckets without changing canonical stored history. Query strings remain forbidden and this resource has no control/write responsibility.

Runtime validation on 2026-09-19 confirmed the initial Web Data API service on Pi localhost `127.0.0.1:3200`: the WW Seasonal Advice resource returned the canonical advisor projection, unsupported POST returned HTTP 405, and no LAN/public listener was introduced. The systemd unit intentionally contains no repository-relative `Documentation=` directive; canonical documentation remains repository-owned rather than encoded as an invalid systemd URL.

Private Pi-hosted frontend is the production EMS website. The first runtime attempt proved the same-origin `/web/*` reverse proxy but also exposed two deployment-boundary defects: a site address alone still produced a wildcard `*:80` listener, and the packaged Caddy service could not serve the webroot below `/home/jeroen`. Caddy was stopped immediately. The corrected repository definition now uses an explicit `bind 192.168.1.42` and stages static V2 files read-only under `/var/www/ems-frontend-v2`; the Web Data API remains `127.0.0.1:3200`. The reserved Wi-Fi address `192.168.1.45`, Docker interfaces and wildcard listeners remain excluded. Remote browser access is to be added separately through Tailscale without Funnel. Deployment source is `deploy/caddy/ems-frontend-v2.Caddyfile`; staging helper is `deploy/install/install_private_frontend_v2.sh`. The Debian Caddy 2.6.2 package does not provide the optional `caddy.logging.writers.journal` module; the private ingress therefore uses Caddy/systemd standard service logging rather than an explicit Caddy `output journal` writer.

Live runtime-data cutover is complete through `GET /web/state/current` (schema `EMS_WEB_STATE_CURRENT_V1`). The endpoint is an explicit allowlisted projection of canonical Pi `/home/jeroen/ems/data/energy-state-v2.json`; the production Live frontend reads this same-origin resource and has no GitHub runtime-data fallback. Runtime validation proved fresh state through both the localhost Web Data API and Caddy while the GitHub energy-state publisher was disabled. The GitHub energy-state publication is retired from production and retained temporarily only for rollback/repository cleanup.

Live V2 PV observability was extended and runtime-validated on 2026-09-19 without changing control ownership. `GET /web/state/current` now allowlists the canonical aggregate PV value, SolarEdge / GoodWe 4200 / GoodWe 2000 power observations, and their existing per-source freshness/age metadata. P1 remains authoritative for realtime grid import/export and flex control; inverter staleness or P1/PV source skew may suppress derived House/Other reconstruction but does not invalidate a fresh P1 measurement. The frontend uses these fields only for read-only PV source detail/freshness presentation and does not poll inverter devices or implement control policy.

Private V2 browser validation established that Web Data API resources reject query strings by design. Frontend read adapters use the stable same-origin resource URL together with `cache: "no-store"`; cache-busting query parameters are forbidden because they convert an otherwise valid resource read into HTTP 400. This preserves the fail-closed API contract without weakening it.

Invoer V2 private read cutover is repository-defined in this release. Invoer V2 reads its operational runtime slice (state timestamp and current WW source) from the private `GET /web/state/current` boundary. Its last accepted Tesla deadline and EMS settings commands are exposed read-only by `GET /web/commands/current`, sourced from the existing canonical GitHub command-transfer files. These command values remain command state, not runtime state, and the Web Data API does not become a command writer. The current canonical energy-state has no `contract` runtime section, so Invoer MUST NOT invent or expose a `contract.mode` runtime field. The private V2 deployment stages `tesla-control-config.json` as a static deployment/config asset for the existing authenticated Worker write route; this does not turn GitHub runtime publication into browser runtime transport. The controller resolves that deployed asset through the same-origin absolute `/settings/config/tesla-control-config.json` path; browser fetch paths MUST NOT depend on the JavaScript module directory. Invoer initializes its single Tesla controller from the exact last accepted command after state render, so unchanged loaded values are represented as `Opgeslagen`/disabled and only explicit edits enable `Opslaan`.

The touched legacy `src/pi/ems-runtime/thermal/` subsystem is removed in this release. Its Quatt collector moves to the canonical integration boundary and its duplicate thermal observer is retired. The active general planner remains temporarily in `src/pi/ems-runtime/planner/` because moving that production path is a separate high-risk migration and is explicitly outside this release.

## 12. Battery boundary

The planned battery architecture is Victron AC-coupled. When commissioned, Victron/DESS remains the primary realtime battery optimizer. Pi/Homey may provide forecasts, load intent and policy constraints but must not create a competing realtime battery optimizer.

## 13. Known technical debt / next validation

- The hardened planner still contains historical compatibility code in `deadline_requirement()` with local `max_a = 16`; current authority uses runtime `deadline_max_a`.
- WW ownership remains more distributed than EV ownership because Homey still carries substantial realtime WW state/safety policy.
- PV forecast quality remains a follow-up item.
- Planner schema V0.3 does not yet embed Homey `state_revision` / `source_sample_at` in the final decision output.
- A dedicated constrained replay optimizer remains future work.
- Legacy backfill collectors remain source-only diagnostic/recovery tooling, not production live collectors.
- Honeywell deployment must continue preserving host-local venv, credentials and OAuth cache.
- Heating Thermal Learning still needs fine-grained empirical room-response data. The provisional 180-minute preheat horizon and <=0.5 °C steps must be evaluated in shadow against actual room temperature, Quatt activity, PV-export capture and rebound/reduced heating around the original Honeywell comfort time before any LIVE heating control is considered.
- Woonkamer/eetkamer grouping is planning metadata and must not be treated as proof of a learned thermal coupling coefficient.

## 14. Architecture enforcement

`scripts/ems_architecture_gate.sh` must continue to enforce at least:

- valid fixed-contract invariants and fail-closed behavior;
- same-release update of this canonical document for architecture-sensitive runtime/systemd/deployment changes;
- no second independent planner-generation owner or physical writer;
- no GitHub dependency in the live Homey↔Pi state/control path;
- target-structure placement for touched Pi code;
- the retired GitHub energy-state publication must not be re-enabled as production Live transport or reintroduce the retired Pi→Homey control-push path;
- Honeywell remains baseline/comfort authority;
- canonical room-heating interpretation remains under `services/pi/state/heating/`;
- canonical preheat candidate construction remains under `services/pi/planner/heating/`, READ_ONLY/SHADOW;
- only Honeywell `UP` demand may be advanced; `DOWN`/`NONE` may not be advanced and Honeywell targets may not be exceeded;
- measured room temperature can suppress unnecessary preheat;
- forecast PV-export evaluation and joint flexible-load allocation remain owned by the Dynamic Pi Planner, not a parallel heating PV schema;
- Quatt acquisition belongs under `services/pi/integrations/quatt/` and is observational for Thermal Learning;
- the retired legacy thermal observer must not reappear as a competing thermal state model;
- no automatic production timers for legacy Homey Insights/day-history polling or alternative Pi-side Homey control publishers.

A failed architecture gate is a hard deployment stop and must not be bypassed in normal operation.
