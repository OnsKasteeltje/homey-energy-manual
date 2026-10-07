# CURRENT EMS STATE

> **Canonical current-state document** for the Raspberry Pi / Homey EMS.
>
> This file describes the intended current operational architecture and logic. Architecture-sensitive runtime, planner, systemd, contract-policy and Homey/Pi responsibility changes must update this document in the same release range.

**Status date:** 2026-10-07
**Verified against:** GitHub `main`, current Pi control architecture, 2026-09-13 Homey/Pi production validation, 2026-09-14 history-chain incident analysis, 2026-09-15 Honeywell read-only recovery/validation and Heating Preheat V0.2 shadow consolidation, 2026-09-17 energy-state website publication recovery, and 2026-09-18 WW BOILER→CV manual-source validation / seasonal-advisor cadence alignment, and 2026-09-19 Homey Core v0.11p schema 2.13 state-contract cutover, plus 2026-10-02 EV Bridge v1.5.4 phase/current cutover, 2026-10-03 v1.5.7 predictive-current promotion, 2026-10-04 historical EV-control reason validation, and 2026-10-04 v1.5.8 production PV-capture tuning, plus 2026-10-06 forecast transport/cadence hardening, and 2026-10-07 Mobile API V1 read-only commissioning/freshness hardening  
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
- Electrical warm-water flex in every Pi planner, including the active Dynamic Pi Planner, is gated by canonical `energy-state-v2.json -> hot_water.mode`: `true` = BOILER and eligible; `false` = CV and ineligible; missing/ambiguous = UNKNOWN and fail closed. CV/UNKNOWN must produce `wwPlanW = 0` and must not reduce residual PV available to other flexloads.
- GitHub is **not** a runtime transport dependency for live Homey ↔ Pi state or control.
- Forecast/planner generation is Pi-local end to end. `ems-forecast-chain.service` may build local planner/history/presentation artifacts, but it must not invoke GitHub planner-runtime publishers. The former `publish_planner_shadow.py` and `publish_dynamic_planner_shadow.py` steps are retired from the production forecast chain; GitHub remains source authority, not a rolling planner-state store.
- Planner GitHub publication retirement phase 2 removes the two Pi publisher sources, the Homey planner-publisher source and the three rolling `docs/data/energy-planner-shadow*.json` artifacts from canonical source. The former Homey Advanced Flow is retained only as disabled `RETIRED | Planner Shadow GitHub publisher` with a single note card and no executable cards. No production planner runtime writer to GitHub remains. Host-local planner publication credentials are retirement-only secrets and must not be used by any production service.
- The former Homey Day Series GitHub publisher (`docs/data/energy-day-v2.json`) is likewise retired from the production architecture. Private History V2 reads Pi-local `/web/history/*` resources; GitHub is not a rolling household-history datastore. The retired Homey Day Series flow is retained only as a disabled note-only marker.
- Deployment backs up the full Pi runtime before explicitly removing retired GitHub publisher runtime files, so source deletion does not trip the unmanaged-file guard and rollback evidence remains available. The shared Homey `GH_Status_Token` value was cleared after both Homey GitHub publishers were retired. Daily PV capture validation remains active and Pi-local, but its former GitHub publisher is retired as well. After this deployment, `/home/jeroen/ems/secrets/github-planner-token` has no production consumer and should be deleted from the Pi.

Operational energy history follows the canonical Homey → Pi state direction. Accepted Core state pushes are archived locally on the Pi; automatic Pi polling of Homey Insights is not a production history transport.


### 1.1 Mobile API V1 — native presentation boundary

The native-mobile presentation boundary is served by the existing Pi Web Data API at `GET /api/mobile/v1/overview`, schema `EMS_MOBILE_OVERVIEW_V1`. It is a read-only aggregation layer only: `readOnly=true`, `presentationOnly=true`, `controlWrites=false` and `physicalWrites=false` are part of the contract. It makes no planner decision, creates no Homey/device write path and does not reintroduce GitHub as a runtime transport dependency.

The canonical Live V2 Pi energy-state projection is mandatory for Mobile V1. Secondary presentation evidence such as WW seasonal advice and Flex Priority SHADOW is best-effort and must never be promoted to live authority merely because it can be read. Failure of the canonical live energy state fails the endpoint closed; failure of a secondary resource degrades only that section.

Mobile V1 applies explicit presentation freshness/consistency semantics to Flex Priority SHADOW. Its `generatedAt` is compared with the canonical Live V2 state time, and the Flex EV `deadlineActive` flag is compared with the canonical live EV deadline state. A Flex source older than 75 minutes is exposed as `STALE`; a semantic deadline-state mismatch is exposed as `INCONSISTENT`. In either case Flex priority owner / EV role / reason and Heating grant fields are suppressed rather than presented as current facts. These checks are presentation guards only and do not alter planner, Gate, actuator or physical-control behavior.

Inactive EV deadline state must not expose an old deadline timestamp or stale remaining-kWh value through Mobile V1. Warm-water mode is normalized at the mobile boundary to `CV`, `BOILER` or `null`; the underlying canonical runtime boolean/source contract is unchanged. The Web Data API remains loopback-bound by default on `127.0.0.1:3200`; direct internet exposure of port 3200 is forbidden. Remote iPhone access must terminate at the separate hardened private HTTPS/authentication boundary.


EV downstream execution observability now extends beyond the EMS control target.
Homey EV Device Health v0.4 performs targeted read-only reads of the Easee
charger and Equalizer and publishes requested/offered current, actual Easee
phase currents/power, target circuit current and Equalizer phase currents/power.
The existing EV Control Pi Push transports that Logic snapshot without device
writes. Pi EV control ingest stores a normalized `downstream_json` projection
inside `ev_control_events`, ensuring offered-current/Equalizer changes create
durable historical evidence even when Gate/Actuator state itself is unchanged.
The AI may therefore distinguish an EMS target mismatch from downstream
charger/load-balancing curtailment; Equalizer attribution remains qualified
unless explicit evidence proves causation.

Household-energy history is derived from cumulative P1/PV counters in `house_energy_intervals`. Cumulative counter rows with quality `held` remain valid monotonic state for derivation and must not truncate the timeline when a PV inverter sleeps or becomes stale after production has stopped. Intervals touching a held counter endpoint are retained with derived quality `held`; counter decreases remain discontinuities and true timing gaps remain `gap`. The Web History API treats `held` intervals as covered energy while preserving the stronger `gap` and `discontinuity` classifications.

### 1.1 Ruimteverwarming — Honeywell baseline, PV-voorverwarming and Thermal Learning

Honeywell/Resideo remains the comfort and schedule authority. The canonical vendor acquisition boundary is `services/pi/integrations/honeywell/`; it produces `EMS_HONEYWELL_SCHEDULE_V0.2` and `EMS_HONEYWELL_STATE_V0.2` without physical writes. The Honeywell schedule collector refreshes the canonical weekly schedule hourly at `:07`; the current-state collector remains on its five-minute cadence.

The canonical EMS interpretation layer is `services/pi/state/heating/build_heating_room_model.py`, schema `EMS_HEATING_ROOM_MODEL_V0.1`. It joins schedule and current room state by stable canonical room key, preserves the actual Honeywell target separately from the scheduled baseline, and classifies the next baseline transition as `UP`, `DOWN` or `NONE` using scheduled current/next targets only. EMS-facing schedule timestamps are offset-aware in `Europe/Amsterdam`.

The canonical shadow preheat layer is `services/pi/planner/heating/build_heating_preheat_plan.py`, schema `EMS_HEATING_PREHEAT_PLAN_V0.2`. It remains **READ_ONLY / SHADOW** and creates no physical writes. PV-preheat scope is explicitly limited to `woonkamer`, `eetkamer`, `keuken` and `serre`; `woonkamer` and `eetkamer` carry common `living_area` grouping metadata. Other Honeywell rooms remain normal baseline/comfort rooms but are outside PV-preheat scope.

Only an upcoming Honeywell `UP` transition can become a preheat candidate. The provisional maximum advancement horizon is 180 minutes. Measured room temperature is decisive: when the later Honeywell target is already satisfied, no preheat candidate exists. When an eligible larger baseline increase is advanced, V0.2 exposes candidate setpoint steps of at most 0.5 °C and skips already-satisfied steps. The later Honeywell target is an absolute ceiling. `DOWN` and `NONE` transitions are never advanced.

Normal Honeywell schedule execution remains baseline comfort demand. EMS creates no new heat demand. PV-voorverwarming may only shift already-planned future Honeywell demand earlier when usable forecast PV-export potential exists; it must not intentionally create grid import merely to absorb energy. `candidate.startAt` remains `null` in the heating-preheat layer. Forecast PV-export evaluation and eventual joint allocation with WW and EV remain the responsibility of the existing Dynamic Pi Planner; this release does **not** modify that planner.

No thermal power, heat-up duration, COP, building heat loss or room-response coefficient is invented by Heating Preheat V0.2. The 180-minute horizon and 0.5 °C advancement steps are shadow guardrails, not learned physical constants.

Heating Preheat V0.3 adds a second, still **READ_ONLY / SHADOW**, safety-state layer at `services/pi/planner/heating/build_heating_preheat_shadow_v0_3.py`. It combines the canonical Heating Room Model, the V0.2 candidate plan and the existing read-only Quatt current artifact into `EMS_HEATING_PREHEAT_SHADOW_V0.3`. It derives house-wide `baselineHeatingDemandPresent` from all canonical Honeywell zones, distinguishes normal baseline heating from pure EMS-preheat eligibility, and checks the existing Quatt observer signal `observerOnly.cvActive` on every shadow evaluation. Normal baseline CV demand is not a preheat fault; CV assist while no baseline demand exists blocks a new pure-preheat increment. Missing, invalid or stale Quatt current state fails closed for new preheat increments only.

Quatt capability `measure_boiler_cic_central_heating_onoff_boiler` is canonically projected by the EMS as `observerOnly.cvActive`. The former EMS alias `boilerAssistOn` is retired because it was ambiguous with domestic hot water and suggested an action rather than an observation. `cvActive` is observation-only: it never lowers a Honeywell target, switches the CV off or suppresses baseline comfort demand. Freshness remains governed by the existing Quatt current artifact `generatedAt` and its existing bounded age. `observerOnly.cvActive.observedAt` records the successful read that produced the value and must be coherent with that same fetch, but it is not a second independent stale gate. Homey's capability `sourceLastUpdated` may remain old while an unchanged boolean is freshly observed and is retained only as source-change provenance.

V0.3 does **not** grant PV opportunity, choose a physical Honeywell target or write any device. `plannerGrant` remains `NOT_EVALUATED` until common Dynamic Pi Planner allocation is implemented, and `controlWrites=false` is part of the schema boundary. V0.3 propagates the V0.2 `maxAdvanceMinutes` value as read-only policy metadata so downstream observability can use the planner-owned horizon without redefining that policy. The local runner `run_heating_preheat_shadow_v0_3.py` consumes only already collected Pi artifacts and publishes derived state under `/home/jeroen/ems/data/`. Its five-minute systemd timer is scheduled after the existing Honeywell-state and Quatt-current collectors and performs no Homey call.

The Quatt current artifact remains an observer-only derived runtime artifact at `/home/jeroen/ems/runtime/thermal/quatt-current.json`. That `runtime/thermal/` compatibility directory is operational state, not generic repository-managed source, and normal Pi deployment MUST preserve it across `rsync --delete`. If the Quatt artifact is temporarily missing or malformed, the V0.3 runner MUST still publish a fresh fail-closed shadow result so downstream layers see `CV status unknown` rather than inheriting an older V0.3 artifact.

The same fresh fail-closed rule applies to invalid Honeywell state/schedule input. A production incident on 2026-10-06 showed `erker_douwe.roomTemperature_C=null`: the Honeywell collector truthfully preserved the missing measurement, but the strict Heating Room Model rejected it as non-numeric and the former V0.3 runner exited, leaving an older V0.3 artifact on disk. V0.3 now catches expected Honeywell source/contract errors and publishes a fresh `EMS_HEATING_PREHEAT_SHADOW_V0.3` with `sourceStatus.status=INVALID`, no reused room observations and no Heating grant. Flex Priority converts that state to `HOLD_UNKNOWN`; V0.4 clears any active shadow progression through `BLOCKED_SOURCE_INVALID`; V0.5 remains fail-closed through its existing source/contract guard. No missing temperature is substituted, carried forward as current, or invented. `ems-health` treats a fresh V0.3 with invalid `sourceStatus` as current `SOURCE_INVALID` degradation rather than healthy freshness.

Frontend V2 separates the thermal analysis surface from cross-domain PV/flex commissioning. The dedicated **Verwarming** page joins, for presentation only, the Honeywell baseline schedule, six hours of canonical `measurements_15m` room-temperature history from `GET /web/heating/temperature-history`, current V0.3 preheat eligibility/window and current V0.4 progression. Honeywell baseline remains visually distinct from measured temperature and the hypothetical V0.4 shadow target. For forward validation, the page may additionally render light potential preheat windows for every future Honeywell `UP` transition already visible in its schedule horizon, using the backend-projected V0.2 `maxAdvanceMinutes`; this preview is presentation-only and does not make those later transitions current V0.3 candidates. Persisted V0.4 opportunity/step history remains authoritative for historical opportunity and dark EMS-intent rendering. The page may draw the current shadow target from its recorded `activeStepStartedAt` through now, but it must not invent historical V0.3/V0.4 events from current snapshots. PV, EV and WW analysis stay outside this page. PV Flex remains the cross-domain priority/energy commissioning surface. All these resources are read-only presentation projections and have zero control impact.

Cross-domain Heating ↔ EV arbitration is prepared separately under `services/pi/planner/joint/build_flex_priority_shadow_v0_1.py`, schema `EMS_PI_FLEX_PRIORITY_SHADOW_V0.1`. This layer is also **READ_ONLY / SHADOW** and does not replace the active Dynamic Pi Planner. It applies the agreed constraint-first/slack rule: a hard EV deadline state (`MUST`) overrides Heating; otherwise the flexible opportunity whose useful window closes first receives first claim when PV opportunity exists. Heating priority reserves **0 W** up front; EV remains eligible for residual realtime PV when Heating is first. P1 remains the realtime opportunity authority, Heating may not intentionally create grid import, and `physicalWriteAllowed=false` is part of the shadow contract. Flex Priority accepts a Heating contender only while the source V0.3 shadow is within the same bounded 420-second freshness horizon used downstream by V0.4. Stale/future Heating input can never be republished as a fresh Heating grant; the arbitration result remains fail-closed for Heating while an already-hard EV `MUST` constraint stays authoritative.

Production Dynamic Pi Planner Heating Grant V0.1 is defined under `services/pi/planner/heating/build_heating_production_grant_v0_1.py`, schema `EMS_PI_DYNAMIC_HEATING_GRANT_V0.1`. It is an authoritative **planner-grant boundary only**, not a second planner and not a physical-control path. The builder joins the current `EMS_PI_DYNAMIC_SHADOW_PLAN_V0.3` slot, V0.3 Heating eligibility and Flex Priority V0.1. Shared forward opportunity is read from the existing slot field `evResidualExportW`; no separate Heating PV pot or watt reservation is introduced and `powerReservationW=0` remains explicit.

Planner authority and realtime execution permission stay deliberately separate. A `PRODUCTION_GRANT` requires current planner validity, fresh/correctly ordered Heating and Flex state, and Flex ownership for Heating. The Pi-local P1 snapshot is advisory evidence only; before any future physical Heating start or progression increment, a downstream Homey execution edge must re-evaluate fresh realtime P1 and fail closed unless export is present and import is absent. Honeywell remains baseline/comfort authority. The grant builder and V0.4 remain `controlWrites=false` and `physicalWriteAllowed=false`.

V0.4 consumes `EMS_PI_DYNAMIC_HEATING_GRANT_V0.1` instead of interpreting Flex `SHADOW_GRANT` directly. The existing V0.4 `:20` service builds the production grant immediately before progression, so no extra timer or parallel planner path is introduced. V0.5 remains downstream and SHADOW-only; the Pi→Homey Heating publisher stays parked and no Honeywell actuator or realtime execution edge is enabled.

The Heating SHADOW cadence is deterministic. A production observation on 2026-10-04 showed that the former relative Flex timer (`OnUnitActiveSec=60s`) could drift into the V0.4 phase: on a V0.3 refresh minute V0.4 could run milliseconds before the new Flex snapshot, making `priorityGenerated < heatingGenerated` and correctly but unnecessarily forcing one fail-closed minute. The canonical active timer phases are therefore: V0.3 at second `:00` on its five-minute refresh minute, Flex Priority at `:10` every minute, V0.4 at `:20`, and V0.5 at `:30`. The historical Homey SHADOW publisher slot remains `:35` but its timer is parked. These local control-chain timers use `AccuracySec=1s`; relative Flex scheduling is forbidden. Freshness/order guards remain unchanged and continue to fail closed if an upstream service actually misses its phase.

A deployment incident on 2026-10-06 is now part of the canonical regression boundary. A transient feature-branch service file contained a literal `\\n` between `ExecStartPre=` and `ExecStart=`; systemd then reported “Service has no ExecStart” and the V0.4 timer entered failed state. Canonical source now requires exactly one physical `ExecStartPre=` line for the production-grant runner and exactly one `ExecStart=` line for V0.4, and the deploy-contract test rejects a literal `\\nExecStart=`. The timer failure was operational fail-closed behavior, not a Heating-decision failure.

Heating Control Gate V0.5 is the first explicit **control-boundary SHADOW** under `services/pi/control/heating/`, schema `EMS_HEATING_CONTROL_GATE_SHADOW_V0.5`. It remains Pi-local and has no Homey/network/device client. It revalidates V0.3/V0.4 freshness/order, V0.4 upstream safety, Honeywell `UP`, CV safety, planner grant, target ceiling and <=0.5 C progression before emitting `HOLD`, `WOULD_SET_TEMP`, `WOULD_KEEP_TEMP` or ownership-bounded `WOULD_RESET_TO_SCHEDULE`. Every command remains hypothetical (`physicalWrite=false`); top-level `controlWrites=false` and `physicalWriteAllowed=false`. Shadow ownership is not physical Honeywell ownership. LIVE promotion requires a separate Pi->Homey contract plus Homey adapter/gate, exactly one Honeywell writer and acknowledgement/readback. V0.5 is a commissioning lifecycle state and must be promoted or retired/archived at LIVE cutover.

Heating commissioning observability is durable before any LIVE promotion. The existing Pi-local `flex_context_snapshots` archive remains schema `EMS_PI_FLEX_CONTEXT_SNAPSHOT_V0.1` for historical-reader compatibility and receives an additive `controlGate` projection containing V0.5 source/check/command/shadow-ownership evidence. Volatile timestamps and freshness ages do not create history rows, but semantic V0.5 transitions such as `WOULD_SET_TEMP`, `WOULD_KEEP_TEMP` and `WOULD_RESET_TO_SCHEDULE` do. The archive cadence runs at `:40`, after V0.4 `:20` and V0.5 `:30`. `ems-health` monitors artifact freshness plus timer/service health for V0.3, Flex Priority V0.1, V0.4 and V0.5. For inactive oneshot services where systemd no longer retains `ExecMainExitTimestamp`, an explicitly mapped Heating function may close only the `NOT_PROVEN` gap using a non-empty timer last-trigger plus a fresh expected artifact while service `Result`/exit status remain successful; actual service failure still degrades immediately.

Heating Pi -> Homey control-contract V0.1 is a proven **SHADOW-only**
boundary. The dedicated Intent -> Adapter -> Gate chain remains installed and
hard-blocked from LIVE execution: `physicalWriteAllowed=false`,
`deviceWrites=false`, `liveExecutionAllowed=false`, and no Heating actuator
exists. The authoritative Dynamic Pi Planner Heating grant now exists, but it feeds only the
local V0.4 SHADOW progression; it does not authorize Homey or Honeywell execution.

The recurring Pi -> Homey Heating publisher is therefore **parked**. Its
systemd timer must remain disabled; `--apply`, `--resume` and
`--runtime-only` all leave it disabled. `--resume` is now only a one-shot
commissioning proof and may perform one paced SHADOW publish/readback cycle.
Normal Heating operation stops at the Pi-local V0.5 artifact. This removes
unnecessary Homey API load and avoids solving transport/rate-limit details for
a SHADOW path that has no production consumer.

The active local cadence is V0.3 `:00` (when due) -> Flex `:10` -> V0.4
`:20` -> V0.5 `:30`. A historical Homey publisher slot remains defined at
`:35` for controlled commissioning only, but its timer is disabled. LIVE
promotion remains blocked until the production-grant-fed SHADOW chain has been
observed cleanly in normal operation and exactly one guarded Honeywell actuator
with acknowledgement/readback and rollback semantics is deliberately implemented.

**Heating continuation checkpoint:** `NEXT_HEATING_STEP_SHADOW_OBSERVATION_BEFORE_EXECUTION_EDGE`.
The next step is observation of the production-grant-fed SHADOW chain; do not
start the Homey execution edge or Honeywell writer before that evidence is reviewed.
The completed/parked SHADOW boundary and exact re-entry sequence are recorded in
`docs/commissioning/heating-homey-shadow-chain-v0.1.md` under
“Continuation checkpoint — 2026-10-04”. That checkpoint is the canonical
handoff to prevent cadence, Homey commissioning, notifier or 429 work from
being repeated without new evidence.

The former legacy `src/pi/ems-runtime/thermal/build_thermal_observer.py` is retired rather than migrated as a parallel thermal model. Its overlapping Honeywell/schedule/room-state responsibility is superseded by the canonical Heating Room Model. There must not be both `EMS_THERMAL_OBSERVER_V0.1` and `EMS_HEATING_ROOM_MODEL_V0.1` as competing descriptions of room-heating state.

Quatt acquisition that remains useful for thermal analysis is canonicalized under `services/pi/integrations/quatt/collect_quatt_current.py`. The production systemd unit points to this target-structure source. Quatt telemetry, canonical room state and historical measurements form the input basis for **Heating Thermal Learning**: empirical evaluation of room response, heat retention, useful advancement horizon and rebound around the original Honeywell comfort time. Thermal Learning is observational; it does not create a second comfort authority or physical writer.

Canonical Thermal Learning objective: use the house only as a thermal buffer
for already scheduled Honeywell heat demand when this can absorb otherwise
exported own PV without material additional grid import over the complete
thermal episode. Reduced PV export alone is not success: retained useful heat,
later heating demand and the subsequent grid-import/export consequence must be
evaluated together. Thermal Learning remains READ_ONLY / SHADOW and supplies
future empirical evidence to the planner; it is not a second planner or
comfort/control authority.


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

GitHub is not runtime-state transport for the production Live website. The former GitHub energy-state publisher, its systemd service/timer, and the derived `docs/data/energy-state-v2.json` publication artifact were removed from the repository on 2026-09-26 after the private Pi-hosted Frontend V2 cutover. They are not supported rollback paths and must not be reintroduced as production transport.

The former MkDocs/GitHub Pages Live, Planner and History operational views are retired. GitHub Pages no longer stages a Frontend V2 preview and no longer depends on Planner/History runtime JSON publication; Frontend V2 is deployed only to the private Pi-hosted production boundary. The Pages site is now a documentation boundary, with Groups/Phases retained temporarily because it still provides unique phase/topology diagnostics. This remaining diagnostic page does not make GitHub an allowed production runtime-state boundary.

### 2.4 Frontend V2 shared navigation governance

Frontend V2 uses one shared main-navigation source: `frontend/shared/navigation.js`. Individual V2 page HTML contains only the navigation mount and must not maintain a second hardcoded menu. The Architecture Gate executes `tests/frontend/test_v2_shared_navigation_contract.py` to enforce this boundary.

For frontend incidents the diagnostic chain is: **GitHub source -> deployed `/var/www/ems-frontend-v2` -> served HTTP -> browser/site data**. When source, deployed files and served HTTP agree, browser cache/site-data remediation must not trigger EMS control, Web Data API or Caddy changes.

Recovery from strongly diverged Git histories must start from a proven good/current base after compare/merge-base/dependency analysis. Force-resetting a recovery branch or blindly transplanting divergent patches is not an accepted recovery method.

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

Production forecast generation has one cadence owner: `ems-forecast-chain.timer` at minutes `:03/:18/:33/:48`. After successful 2026-10-06 Pi validation of the atomic chain, the former standalone weather/PV timers **and services** were retired completely: `ems-weather-forecast.timer/.service` and `ems-pv-forecast.timer/.service` are absent from the canonical `deploy/systemd/` set and are removed from `/etc/systemd/system` by `scripts/deploy_ems_pi.sh`. Deployment backs up any still-installed copies before removal; rollback source remains available through deployment backups and Git history, not as dormant production units. `ems-health` monitors forecast execution through `forecastChain`, while weather/PV/Quatt artifacts remain independently freshness-checked under EMS DATA.

Open-Meteo transport is shared by the production weather and PV fetchers through `services/pi/forecast/open_meteo_transport.py` (deployed as `/home/jeroen/ems/runtime/forecast/open_meteo_transport.py`). Each request keeps the existing 20-second timeout and may perform exactly one retry after 2 seconds only for transient transport failures (including timeout/TLS/connectivity/DNS-class `URLError`) or HTTP 429/5xx. Certificate-verification failures and other non-transient HTTP 4xx fail immediately. A failed second attempt propagates and aborts the atomic chain; no stale forecast is relabelled as fresh and no fallback bypasses the normal freshness guards.

This policy was introduced after the 2026-10-05/06 incident analysis proved two separate `_ssl.c:1012` handshake timeouts: the 23:33 forecast-chain run had already completed planner-axis, weather import and Quatt forecast before `fetch_pv_forecast.py` timed out on its Open-Meteo HTTPS handshake; the 04:46 legacy standalone weather run timed out on the first `fetch_weather_forecast.py` Open-Meteo handshake. Both later recovered without intervention. The failure class is therefore treated as transient external connectivity, not planner/data corruption.

EV opportunity forecasting is phase-aware from 2026-10-01. The strategic 15-minute planner mirrors the production realtime phase-entry bands: OFF→1P at 1500 W residual PV and OFF/1P→3P at 4400 W. Within 1P it plans 6–16 A as 230 W/A (1380–3680 W); within 3P it plans 6–16 A as 690 W/A (4140–11040 W). Opportunity targets never intentionally exceed forecast residual PV. The realtime stop/downshift hysteresis (1P stop below 1100 W on the rolling 2-minute signal, 3P leave below 3600 W) and the 120-second minimum mode dwell remain Homey executor responsibilities and are not simulated as sub-slot state by the 15-minute planner. EV deadline charging remains a separate hard-constraint path and is forced to 3P. This removes the former planner-only 3P abstraction in which 6 A was always treated as 4140 W.

Bridge v1.5.9 is **LIVE** on stable Homey Advanced Flow `8bf53fdb-76f4-47db-8ccb-773ac515f06e` as `EM v2 | 20 Power Intent | PI Dynamic Planner Bridge v1.5.9 ADAPTIVE UPSCALE [READY]`. Canonical source is `apps/homey/control/ev/pi-dynamic-planner-bridge-v1.5.9.adaptive-upscale.js`. The 2026-10-04 same-day replay showed that most residual PV export occurred while the EV was already charging rather than because the planner missed the opportunity window, so v1.5.9 changes only same-phase 3P upward current response. Phase thresholds, OFF re-entry dwell, 1P→3P dwell, deadline force and fast down-regulation remain unchanged. The normal bounds stay +3 A in 1P and +2 A in 3P; only an already-confirmed 3P session may use up to +4 A when instantaneous P1 export, the ready 2-minute rolling available-power signal, the instantaneous predictive desired current and settled physical Easee current all support the same larger step. The diagnostic reason is `PREDICTIVE_UP_ADAPTIVE_EXPORT`; controller diagnostics are `EM2_EV_PHASE_CURRENT_CONTROLLER_V0.4` and expose rolling desired current, current export, candidate adaptive step and applied step. Adapter/Gate/Writer contracts remain unchanged and writer v0.4.5 remains the sole physical Easee writer. The exact targeted post-write readback verified stable Flow ID, enabled=true, broken=false, five cards, byte-identical non-script cards and exact v1.5.9 script source.

For opportunity stop/restart semantics, a planner quarter-hour marked `RUN / OPPORTUNITY` is permission and strategic allocation, not a command to charge continuously through that slot. The Homey realtime executor may drive the EV to `OFF/IDLE` when the rolling available-power signal falls below the phase-specific stop threshold. In particular, 1P stops below 1100 W rolling available power. Restart from OFF requires the rolling signal to recover to at least 1500 W, instantaneous power sufficient for minimum 1P, and the v1.5.8 120-second OFF re-entry dwell. Promotion from 1P to 3P requires rolling available power of at least 4400 W, instantaneous 3P/6 A viability and the separate 180-second 1P→3P dwell. The 2026-10-04 12:45–13:00 event demonstrated why planner opportunity and realtime physical execution must be diagnosed separately; later same-day minute telemetry showed that the former unified 300-second upward dwell left material PV export during rapid irradiance recovery, motivating the bounded v1.5.8 reduction.

Heating Preheat V0.2 does not alter the active Dynamic Pi Planner. It exposes only validated shadow advancement candidates; PV-slot selection and any later competition/allocation between WW, heating-preheat and EV remain outside the heating candidate builder.

Planner decisions are archived best-effort in `/home/jeroen/ems/data/planner-history.sqlite`; measured actuals remain in `/home/jeroen/ems/data/ems-history.sqlite`. Retrospective performance analysis must distinguish measured actuals, archived decision context and any unconstrained upper-bound benchmark from a future constrained replay optimum.

Runtime validation on 2026-10-04 exposed that canonical operational power
measurements are approximately five-minute cadence, while the initial V0.1
candidate rejected every measurement interval over 120 seconds and therefore
integrated zero hours. The cadence correction accepts canonical measurement
intervals up to 600 seconds for energy integration, keeps 120 seconds as the
preferred attribution resolution and segments coarse intervals at durable EV
control state-change boundaries. The resulting replay integrated 22.5 hours
and reproduced 6.8958 kWh observed export. Follow-up inspection showed that
`ev_control_events` is intentionally semantically deduplicated: absence of a
new row means no normalized control-state change, not a missing heartbeat.
V0.1.1 therefore loads the latest pre-day state as a baseline and carries a
known control state until the next durable change; age over 90 seconds reduces
otherwise-HIGH confidence to MEDIUM instead of erasing the state. V0.1.1 also
requires strictly positive proven additional capture before an actuator failure
may be labelled `REAL_MISSED_OPPORTUNITY`; otherwise it is constraint-driven.
This preserves useful five-minute energy evidence without claiming direct
120/180-second measurement precision.

Constrained Replay V0.1.1 is now runtime validated as the first deterministic
short-timescale constrained replay. Canonical source is
`services/pi/history/constrained_replay_v0_1.py`, schema
`EMS_PI_CONSTRAINED_REPLAY_V0.1.1`, with explicit scope `EV_EXPORT_ONLY`.
It reads only `ems-history.sqlite/measurements`, durable
`ev_control_events` and `semantic_events`; it performs no Homey/network,
planner or device/control write. It classifies time-aligned observed export as
`UNAVOIDABLE_EXPORT`, `CONSTRAINT_DRIVEN_EXPORT`,
`REAL_MISSED_OPPORTUNITY` or `INSUFFICIENT_EVIDENCE`. The classification
is deterministic and conservative: missing/stale control evidence is never
promoted into a performance conclusion. In V0.1, “unavoidable” is explicitly
EV-relative and must not be generalized to WW/Heating/appliance/battery
flexibility. The existing PV-surplus absorption backtest remains the separate
longer-horizon technical allocation/capacity backtest and is not replaced by
this incident/performance replay. Runtime validation on the Pi is required
before the replay is exposed as AI evidence.

## 5. Current control endpoint

The Pi exposes `GET /control/current`. A valid production response uses schema `EMS_PI_CONTROL_COMMAND_V0.1`, is bounded to the current quarter-hour slot and planner validity, and fails closed on stale or invalid planner input. The endpoint is a readiness/command endpoint, not a second authority selector.

## 6. Current state ingest and history endpoint

The Pi exposes `POST /state/energy` for authenticated Homey→Pi state ingestion. Missing/incorrect authentication, malformed state, stale state, replayed state and non-approved schema versions fail closed for current-state acceptance. Exact schema-version compatibility is owned here rather than in the transport layer; the current approved set is `{2.12, 2.13}`. Operational history insertion is idempotent; a local history-archive failure must not invalidate otherwise fresh accepted live state.

Legacy Homey Insights/day-history polling may remain only as explicit backfill/diagnostic tooling and must not run as an automatic production history transport.

For Energiehistorie V2, Homey Core schema 2.13 cumulative counters are archived as first-class observations in the same canonical `measurements` table: P1 `energy_import_kwh` / `energy_export_kwh` and per-inverter `energy_produced_kwh` for SolarEdge, GoodWe 4200 and GoodWe 2000. Period energy is derived from validated non-negative counter deltas; counter resets/replacements/rollovers must be surfaced as discontinuities rather than negative energy. Household consumption is derived as `grid import + PV production - grid export`. The three PV counters remain separate through the history contract so Frontend V2 can provide PV hover/detail per inverter as well as aggregate PV. Realtime control continues to use P1/inverter power and freshness; cumulative counters do not become a realtime control input.

Derived household history is owned by `services/pi/history/build_house_energy_history.py`. It creates `house_energy_intervals` from consecutive complete five-counter snapshots. The derived table is rebuilt transactionally from canonical cumulative measurements on each builder run, so obsolete rows from superseded derivation semantics cannot persist. Positive source samples less than one second after the current baseline are coalesced rather than misclassified as non-forward time: the earlier baseline is retained and any cumulative counter delta is preserved into the next representable interval. `NON_FORWARD_TIME` is reserved for genuinely non-increasing source time. Each interval retains P1 import/export and all three PV deltas separately, plus aggregate PV and `house_kwh = import_kwh + pv_total_kwh - export_kwh`. A counter decrease is stored as a discontinuity with null energy values, never as negative energy. Gap classification is source-resolution-aware: normal coarse backfill intervals are not mislabeled as missing data, while intervals materially larger than their source resolution remain numerically derivable but are explicitly quality-marked `gap`. Counter decreases larger than the defined floating-point tolerance remain discontinuities; insignificant counter rounding noise is not treated as a reset. Presentation/aggregation must surface reduced coverage rather than silently treating it as complete.

Historical cumulative counters may be seeded only through the explicit maintenance importer `tools/maintenance/homey/import_energy_counter_backfill.py`. The importer consumes a captured Homey Insights export; it has no Homey connection, service or timer and therefore does not create a production polling path. Imported observations are marked `quality=backfill` with their source resolution. Normal ongoing history remains exclusively push-fed through Homey Core -> Pi ingress.

Derived operational history is rebuilt locally from canonical `measurements` and is deliberately independent from live state ingest and control. `services/pi/history/build_15m_history.py` owns deterministic raw-to-quarter-hour aggregation into `measurements_15m`; `services/pi/history/build_daily_energy_history.py` owns raw-to-daily boiler energy aggregation into `daily_energy_history`. For power metrics, `source_resolution_seconds` is a maximum validity horizon, not an energy-duration multiplier for every stored row: quarter-hour energy is integrated over the actual elapsed interval to the next source sample, capped by that validity horizon and split at quarter-hour boundaries. Power-slot completeness is therefore based on covered seconds rather than raw sample count; a source gap is never filled beyond the declared validity horizon. `measurements_15m` remains a fully derived projection and is rebuilt transactionally so values created under superseded aggregation semantics cannot survive. Production scheduling is owned by independent `ems-history-15m.timer` and `ems-history-daily.timer` units. `ems-history-15m.service` runs both the canonical 15-minute aggregation and `build_house_energy_history.py` at :02, :17, :32 and :47 each hour, so newly push-archived cumulative counters are continuously projected into `house_energy_intervals` without Homey polling or a second raw-history writer. Failure of either derived-history builder must remain observable but must not block Homey→Pi state ingest, planning, `/control/current` or Homey execution. These builders must not poll Homey or create an alternative raw-history writer. Runtime validation on 2026-09-19 at 23:02 CEST confirmed the timer-triggered production run completed both builders successfully and advanced canonical `house_energy_intervals` automatically to 1068 intervals, with the newest derived interval ending at 23:02 CEST and quality `observed`.

## 7. Tesla production chain

Tesla charging remains split between Pi planning and Homey guarded execution. Opportunity charging uses residual PV subject to executable Easee limits; explicit deadline charging is a hard requirement and may use grid energy when required. Homey may trim within the Pi envelope but must not become a second independent planner. The guarded EV actuator remains the sole automatic physical Easee writer in the production EV chain.

Production runs EV phase writer v0.4.5 on the existing sole-writer Advanced Flow `fea23193-a03f-49dd-9780-7e72ee48747d` as `EM v2 | 60 Actuator | EV Power v0.4.5 AUTH-ALERT [LIVE]`. The bounded writer preserves the v0.4.x pause → phase command → confirmation/deadtime → temporary circuit-cap → resume/current → circuit-cap-restore sequence for true 1P↔3P transitions, while same-phase current changes remain direct bounded current writes. Electrical phase telemetry is the strongest confirmation when available, with Easee cloud phase observation used as the bounded transition command/readback path. v0.4.4 added the final pause read that avoids false timeout at the edge of the strict polling window; v0.4.5 adds typed Easee-authentication failures plus deduplicated Owner push / Timeline fallback for terminal auth incidents. Auth alerting is observability only and never bypasses fail-closed actuator behavior or creates a second writer.

EV deadline lifecycle and derived progress state are Pi-owned. Canonical charging telemetry remains Homey Core push-fed; the Pi must not poll Homey to keep deadline state alive. Website deadline commands are polled from the durable GitHub command artifact by `ems-ev-deadline-command.service`. Every successful command-fetch invocation directly schedules `ems-ev-deadline-state.service` through systemd `OnSuccess=`, so a newly accepted request does not depend on a separate timer or filesystem event before `/control/current` can expose the new deadline contract. The existing command-file `PathChanged=` watch remains an additional event trigger, not the primary hand-off guarantee. Because accepted `energy-state-v2.json` is atomically replaced, its systemd `PathChanged=` watch is likewise best-effort only and is not the sole liveness mechanism. A 60-second Pi-local deadline-state watchdog may re-run the read-only derived-state builder against the last accepted canonical state. Reprocessing an unchanged telemetry timestamp must integrate zero additional charging energy. Derived-state refresh age and source-telemetry freshness are separate safety concepts: the watchdog may keep derived state current, but stale canonical Homey telemetry must still fail closed under the existing telemetry-age bound.

Live deadline validation on 2026-10-01 exposed a command-ingress latency boundary before Pi acceptance: the Cloudflare Worker committed a new deadline to GitHub at approximately 22:08, while the 60-second Pi fetcher continued to observe the previous request until 22:12:28. Once accepted, the Pi derived deadline state became `TRACKING` within roughly one second and the Homey executor subsequently applied the requested 3P/8 A deadline command. The current Pi ingress still reads the `raw.githubusercontent.com/.../main/...` branch URL, so edge/cache freshness can dominate command latency even while the local timer runs correctly. This is command-transfer technical debt only; it does not change Pi deadline ownership or Homey executor ownership. Migration of the Pi read path to the GitHub Contents REST API is the planned corrective action and must be validated before the raw branch URL is retired.

## 8. Warm-water production chain

WW comfort remains a hard constraint above optimization. The Pi schedules remaining required heating before the comfort deadline and prefers useful PV periods. Homey translates the Power Intent through the WW adapter/gate chain; the guarded Warm Water Actuator remains the physical boiler writer. Source mode, kill switch, freshness and current device state are checked before writes.

Electrical WW flex is now hard-gated by canonical runtime source `energy-state-v2.json -> hot_water.mode`: `true = BOILER` permits electrical WW planning, while `false = CV` and missing/ambiguous source state fail closed to zero electrical WW allocation. When source is CV or UNKNOWN, the Pi WW plan retains forecast demand only as observability but sets electrical required/allocated energy to zero and all WW plan slots to `0 W`. WW therefore cannot reserve PV or compete with EV/heating-preheat unless the active source is explicitly BOILER.

The Pi WW Seasonal Source Advisor is read-only and manual-switch-only. It runs daily at 00:05 Europe/Amsterdam against canonical Pi-local history, so the just-completed local calendar day is immediately eligible for `completeDaysOnly` analysis. It has no dependency on the retired `ems-day-history.service` or other Homey Insights polling; source-switch advice requires the configured multi-day confirmation before notification and never performs a physical source switch. Confirmation is counted once per unique analysis `asOfDate`; reruns, restarts and persistent-timer catch-up executions for the same analysis day are idempotent and must not advance the confirmation streak. On 2026-09-18 the manual BOILER→CV change was validated end-to-end: Homey `WW_Boilermodus=false` resolved to Pi `currentMode=CV`, the advisor retained `KEEP_CURRENT` because CV was economically preferable, and the prior switch-to-CV confirmation streak reset to 0 without any automatic source write.

### 8.1 Quooker flex — LIVE

Quooker is geïntegreerd als eenvoudige flexload zonder thermisch state-model. De Pi blijft planner-owner en publiceert per current slot een `targets.quooker` envelope via `/control/current`: op werkdagen `OPPORTUNITY` vóór 17:00, `FORCED_ON` van 17:00–18:00 en daarna `OFF`; in het weekend `OPPORTUNITY` vóór 13:00, `FORCED_ON` van 13:00–14:00 en daarna `OFF`. Het gemodelleerde momentane verwarmingsvermogen blijft 1580 W.

Historische P1-analyse over fysieke legacy-inschakelmomenten van 6–30 september 2026 kalibreert de normale Quooker-opwarming op ongeveer **0,25 kWh**. De planner behandelt dit daarom als een dagelijks energy-budget van `0.25 kWh`, niet als 1580 W gedurende het volledige forced uur. Met kwartierslots wordt exact één forced-slot als `1000 W` gemiddeld planvermogen gereserveerd (= 0,25 kWh); de overige forced-slots reserveren geen extra Quooker-energie. De 1580 W blijft uitsluitend de momentane heating/headroom-parameter. Dit komt overeen met circa 9,5 minuut verwarmen bij 1580 W. De Homey realtime opportunity- en forced-on envelope blijft ongewijzigd.

Homey vertaalt dit envelope via de actieve PI bridge naar `EM2_Power_Intent.targets.quooker`. `EM v2 | 60 Adapter | Quooker Power v0.1 SHADOW` gebruikt binnen `OPPORTUNITY` de bestaande `EM2_P1_Rolling` 120-secondenmeting: start bij `avgGridW <= -1250 W` en behoud ON totdat `avgGridW >= +600 W`. Het resultaat wordt gepubliceerd als `EM2_Control_Quooker`.

Voor retrospectieve shadowvalidatie publiceert de adapter numerieke Insights-signalen `EM2_Quooker_Shadow_AvgGridW`, `EM2_Quooker_Shadow_Mode_Code` (`0=OFF`, `1=OPPORTUNITY`, `2=FORCED_ON`) en `EM2_Quooker_Shadow_Target_Code` (`0=OFF`, `1=ON`). `Mode_Code` volgt de effectieve fail-closed gevalideerde mode, niet de ruwe Pi-mode. De bestaande boolean `EM2_Quooker_Shadow_Target_On` blijft beschikbaar voor actuele Logic-status, maar historische analyse gebruikt de numerieke target-code.

`EM v2 | 60 Actuator | Quooker v0.2 LIVE` (stabiele Flow ID `2d0ca017-0d35-4071-bd06-87742032c399`) is sinds 2 oktober 2026 de sole physical writer voor het Homey-device `Cooker` (device ID `42992d14-c4e4-43fc-aaf0-29a73a8e2eb9`). De actuator consumeert `EM2_Control_Quooker`, schrijft idempotent alleen bij een stateverschil en failt closed naar OFF bij ongeldig of stale control. De drie legacy tijdflows `Waterkoker weekend Aan`, `Waterkoker doordeweeks Aan` en `Waterkoker Uit` zijn in dezelfde cutover disabled en blijven uitsluitend rollback-evidence; zij mogen niet naast de LIVE-actuator actief zijn.

Quooker-vermogensobservatie wordt sinds 3 oktober 2026 geleverd door `EM v2 | 01 Quooker Detector | v0.5 LIVE OBSERVE-ONLY` (Flow ID `939a347f-0b19-4c3d-98d3-77faa01fce0b`). Deze detector verandert geen Quooker-control of planner-ownership. Cooker `onoff` blijft autoritatief voor OFF/ON; HEATING vereist een korte geïsoleerde L3-stap (start 1300..1900 W) terwijl L1/L2 binnen de side-phase guard blijven. Een EV-achtige driefasenstap wordt daardoor afgewezen. HEATING heeft daarnaast een harde 90-seconden fail-safe. De flow gebruikt geen brede `getVariables()`/`getDevices()` collection reads en verricht geen fysieke device writes. De voormalige v0.4 detector (Flow ID `e291cf14-0b92-4cef-ae8b-a699692b6c9a`) is disabled rollback; maximaal één detectorversie mag enabled zijn.

De read-only Quooker-evidenceketen naar de Pi is sinds 4 oktober 2026 LIVE-actuator-aware. `quooker_control_events` bewaart actuator-schema en -mode plus de v0.2-velden `actualOnBefore`, `actualOnAfter`, `physicalWritePerformed` en `writeError`; historische v0.1-SHADOW-velden blijven compatibel. De AI-analyse gebruikt actuator `mode` als autoriteit: een SHADOW target/would-write is geen device-write, terwijl `mode=LIVE` met `physicalWritePerformed=true` direct bewijs is van een door Homey uitgevoerde Cooker-write. Voor reeds vóór deze schemafix gearchiveerde v0.2-events mag uitsluitend het bewaarde raw evidence JSON als fallback worden gebruikt; detector-HEATING alleen bewijst verwarming, niet de fysieke control-write.

## 9. Live cutover validation

The controlled 2026-09-12 cutover validated Pi→Homey→Tesla and Pi→Homey→boiler end-to-end. The Homey→Pi state direction was validated in production on 2026-09-13 using genuinely fresh Homey Core state. Synthetic freshness must not be used as production evidence.

The 2026-09-14 history incident demonstrated that a separate Homey Insights pull chain is unsuitable as the production history transport; accepted Homey state pushes are archived locally instead.

Heating Preheat V0.3 remains shadow-only. This release additionally defines deployable Heating Preheat Progression V0.4 SHADOW downstream of V0.3 and Flex Priority Shadow V0.1. V0.4 transition metadata is event-based: when progression state/target/reach/completion is unchanged, `lastTransition` and `lastTransitionAt` are preserved rather than refreshed every minute. V0.4 now persists two bounded 48-hour histories per scoped room in the same local artifact: `opportunityHistory` retains every observed Honeywell-UP preheat window (open/close timestamps and future Honeywell target) even if no grant occurs, while `stepHistory` retains closed shadow-target intervals and their outcomes/reasons. The current active shadow step remains represented by the existing active-step fields until it closes. These are read-only analysis records for Frontend V2; historical opportunity or intent intervals must not be reconstructed heuristically in the browser. The first opportunity-history deployment may idempotently seed only the preceding 48 hours from the canonical Honeywell weekly schedule via the versioned deploy migration, after which V0.4 retains windows prospectively. Neither history nor the bootstrap migration creates a second planner/control path. V0.4 persists only hypothetical active <=0.5 C steps in `/home/jeroen/ems/data/heating-preheat-progression-shadow-v0.4.json`, advances only after measured room-temperature proof, requires a fresh/consistent central planner grant for start and advancement, and synchronizes subsequent advancement across selected grouped rooms. Loss of grant or a safety guard can hold/block progression, but LIVE rollback behavior is deliberately undefined in shadow. No Honeywell, Homey, Quatt, CV, Power Intent or other physical control is introduced, so no heating-control cutover is claimed. Runtime commissioning of the V0.4 timer remains required before the layer is treated as validated production observability.

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

Canonical PV Forecast V2 source lives under `services/pi/forecast/` and is deployed explicitly to the stable runtime subtree `/home/jeroen/ems/runtime/forecast/`. The generic `src/pi/ems-runtime` rsync must exclude this target-managed subtree; deployment and drift validation independently map and compare the complete forecast source so `ems-pv-forecast-v2-shadow.service` cannot reference a file that deployment has deleted. This mapping closes the 2026-09-26 stale-planner incident in which the timer remained active but forecast generation failed after a Pi deployment removed `/home/jeroen/ems/runtime/forecast/pv/build_pv_forecast_v2.py`; the last valid forecast consequently remained at 19:49 CEST until the missing runtime source was diagnosed.

The former GitHub website energy-state publisher has been removed. `services/pi/integrations/github/` remains only for the separate authenticated command-transfer integration; it must not regain an energy-state publication role.

The target Frontend V2 operational-data boundary is the dedicated read-only EMS Web Data API under `services/pi/api/web-data/`. It is separate in responsibility and failure behaviour from the existing runtime/control status API. The Web Data API is presentation transport only: it has no EMS policy, optimizer, Homey/device write or actuator path. The initial resource is WW Seasonal Advice; the same boundary is intended to serve later Live, Planner, History and observability resources through explicitly versioned allowlisted contracts.

The Web Data API security baseline is mandatory and canonical in `docs/architecture/web-data-api-security.md`. The origin is private and binds locally by default. Frontend V2 is now explicitly targeted as a private Pi-hosted website: local browser access is limited to the trusted home LAN and remote access to authorized devices/users through the Tailscale tailnet. No router port-forward, public internet ingress, Tailscale Funnel or Cloudflare/public tunnel is part of the current target architecture. The preferred final browser/API path is same-origin through the Pi private web ingress while the API remains localhost-scoped. GitHub Pages is transitional during migration, not the target V2 runtime host. User command/write interfaces remain separate. Creating this foundation does not disable any existing GitHub runtime publication or change the live Homey↔Pi control path.

The canonical Pi deploy/drift boundary explicitly manages `services/pi/api/web-data/` as `/home/jeroen/ems/runtime/web-data-api`; generic runtime rsync excludes that target-managed directory so deployment cannot delete the Web Data API working directory. Drift validation compares this runtime subtree against its canonical source. The history database is opened by this read-only service with SQLite URI `mode=ro&immutable=1`, matching the systemd read-only sandbox and preventing journal/WAL write attempts.

History V2 is repository-defined on the same read-only boundary through `GET /web/history/day/YYYY-MM-DD`, `/week/YYYY-MM-DD`, `/month/YYYY-MM` and `/year/YYYY` using schema `EMS_WEB_HISTORY_V1`. These resources query only canonical `house_energy_intervals`, use Europe/Amsterdam calendar boundaries, expose house/PV/import/export plus all three inverter contributions, and explicitly report coverage, gaps and discontinuities. Day series are hourly, week/month series daily and year series monthly; coarse source intervals are apportioned across presentation buckets without changing canonical stored history. Query strings remain forbidden and this resource has no control/write responsibility.

PV & Flex V2 uses the same read-only Web Data API boundary through `GET /web/analysis/pv-flex/day/YYYY-MM-DD`. Historical household-energy intervals accept canonical `observed` and `held` quality: a `held` cumulative-counter endpoint may still preserve a valid energy delta and is therefore not discarded as a discontinuity. `coverage=0` remains missing evidence and the frontend must not present it as a physical zero. Actual Tesla and boiler device power comes from canonical `measurements_15m`; the canonical aggregation quality values for these device rows are `complete` and `partial`, and both are valid presentation evidence. Persisted Heating Preheat V0.4 `opportunityHistory` and `stepHistory`, plus the explicitly recorded current active-step interval, are projected presentation-only onto the same 15-minute PV & Flex timeline. Historical Heating opportunity or intent is never reconstructed from a current snapshot. This resource remains observability-only and does not change P1 realtime authority, planner ownership or any Homey/device write path.

Runtime validation on 2026-09-19 confirmed the initial Web Data API service on Pi localhost `127.0.0.1:3200`: the WW Seasonal Advice resource returned the canonical advisor projection, unsupported POST returned HTTP 405, and no LAN/public listener was introduced. The systemd unit intentionally contains no repository-relative `Documentation=` directive; canonical documentation remains repository-owned rather than encoded as an invalid systemd URL.

Private Pi-hosted frontend is the production EMS website. The first runtime attempt proved the same-origin `/web/*` reverse proxy but also exposed two deployment-boundary defects: a site address alone still produced a wildcard `*:80` listener, and the packaged Caddy service could not serve the webroot below `/home/jeroen`. Caddy was stopped immediately. The corrected repository definition now uses an explicit `bind 192.168.1.42` and stages static V2 files read-only under `/var/www/ems-frontend-v2`; the Web Data API remains `127.0.0.1:3200`. The reserved Wi-Fi address `192.168.1.45`, Docker interfaces and wildcard listeners remain excluded. Remote browser access is to be added separately through Tailscale without Funnel. Deployment source is `deploy/caddy/ems-frontend-v2.Caddyfile`; staging helper is `deploy/install/install_private_frontend_v2.sh`. The Debian Caddy 2.6.2 package does not provide the optional `caddy.logging.writers.journal` module; the private ingress therefore uses Caddy/systemd standard service logging rather than an explicit Caddy `output journal` writer.

Live runtime-data cutover is complete through `GET /web/state/current` (schema `EMS_WEB_STATE_CURRENT_V1`). The endpoint is an explicit allowlisted projection of canonical Pi `/home/jeroen/ems/data/energy-state-v2.json`; the production Live frontend reads this same-origin resource and has no GitHub runtime-data fallback. Runtime validation proved fresh state through both the localhost Web Data API and Caddy. The former GitHub energy-state publication path has now been fully removed from repository and deployment definitions.

Live V2 PV observability was extended and runtime-validated on 2026-09-19 without changing control ownership. `GET /web/state/current` now allowlists the canonical aggregate PV value, SolarEdge / GoodWe 4200 / GoodWe 2000 power observations, and their existing per-source freshness/age metadata. P1 remains authoritative for realtime grid import/export and flex control; inverter staleness or P1/PV source skew may suppress derived House/Other reconstruction but does not invalidate a fresh P1 measurement. The frontend uses these fields only for read-only PV source detail/freshness presentation and does not poll inverter devices or implement control policy.

Private V2 browser validation established that Web Data API resources reject query strings by design. Frontend read adapters use the stable same-origin resource URL together with `cache: "no-store"`; cache-busting query parameters are forbidden because they convert an otherwise valid resource read into HTTP 400. This preserves the fail-closed API contract without weakening it.

Invoer V2 private read cutover is repository-defined in this release. Invoer V2 reads its operational runtime slice (state timestamp and current WW source) from the private `GET /web/state/current` boundary. Its last accepted Tesla deadline and EMS settings commands are exposed read-only by `GET /web/commands/current`, sourced from the existing canonical GitHub command-transfer files. These command values remain command state, not runtime state, and the Web Data API does not become a command writer. The current canonical energy-state has no `contract` runtime section, so Invoer MUST NOT invent or expose a `contract.mode` runtime field. The private V2 deployment stages `tesla-control-config.json` as a static deployment/config asset for the existing authenticated Worker write route; this does not turn GitHub runtime publication into browser runtime transport. The controller resolves that deployed asset through the same-origin absolute `/settings/config/tesla-control-config.json` path; browser fetch paths MUST NOT depend on the JavaScript module directory. Invoer initializes its single Tesla controller from the exact last accepted command after state render, so unchanged loaded values are represented as `Opgeslagen`/disabled and only explicit edits enable `Opslaan`.

The touched legacy `src/pi/ems-runtime/thermal/` subsystem is removed in this release. Its Quatt collector moves to the canonical integration boundary and its duplicate thermal observer is retired. The active general planner remains temporarily in `src/pi/ems-runtime/planner/` because moving that production path is a separate high-risk migration and is explicitly outside this release.


### EV phase writer failed-transition recovery

The 2026-09-27 live EV incident established that planner/P1/Bridge/Adapter/Gate
were healthy while the sole Homey EV actuator remained fail-closed because a
temporary 6 A dynamic circuit cap from an interrupted phase/start transition had
not been restored. The v0.4.2 recovery path could clear its captured
`originalCircuitA` before physical circuit-limit restoration was confirmed,
leaving a later positive 1P command blocked by
`CIRCUIT_LIMIT_BELOW_REQUEST`.

The repository correction is writer v0.4.3. Failed transitions retain the
captured pre-transition circuit limit, restore it through the existing sole
Homey actuator path while the session is safely paused, confirm readback, and
only then return to STABLE. If a legacy/orphaned state has already lost the
captured baseline, runtime remains fail-closed and does not guess a value. The
guarded v0.4.3 upgrade helper can deploy in that diagnosed paused/zero-load
state; restoring the independently proven pre-transition baseline remains an
explicit operator recovery step.

This change does not alter Pi planner authority, realtime P1 authority, phase
thresholds, Adapter/Gate semantics, deadline policy, or the single-writer
boundary. The guarded v0.4.3 upgrade and the one-time recovery of the proven
20 A pre-transition baseline were completed and physically validated on
2026-09-27.


### EV bounded phase-transition execution

A natural 1P→3P opportunity on 2026-09-27 proved that the phase selector and
hysteresis were correct but that v0.4.3 continuation was not reliable. The
writer physically paused Easee and persisted `PAUSING`, but its call to
self-trigger the same Advanced Flow did not reliably produce the next actuator
invocation. Manual/external triggers advanced the writer immediately. During the
pause, changing PV caused the requested mode/current to move again, extending
the pause unnecessarily.

Repository v0.4.4 removes inter-stage self-retrigger. A phase change is executed
as one bounded HomeyScript transaction with explicit readback timeouts:
pause/confirm, phase command/confirm, 5 s deadtime, temporary circuit cap,
resume, current application, Easee command acceptance, and restoration of the
captured circuit baseline. The writer re-reads the existing
Bridge/Adapter/Gate command while safely paused so a changed PV command can be
absorbed before resume. A short RUNNING lock prevents concurrent Gate-triggered
executions from becoming a second writer.

No planner ownership, P1 authority, phase thresholds, deadline semantics,
Adapter/Gate contract, Easee physical-phase ownership, or single-writer boundary
changes. The first v0.4.4 deployment attempt rolled back automatically because
HomeyScript has no `setTimeout`; the bounded source now uses the native global
`await wait(ms)` primitive and the upgrader rejects unsupported timer usage.
A second guarded v0.4.4 attempt then showed that the deployment helper had accumulated runtime-policy checks that were not deployment safety requirements. The v0.4.4 deploy guard is now deliberately minimal: it refuses replacement only while the sole writer has an active `RUNNING` bounded transition or while the Easee circuit target is within the temporary EV transition-cap range (6..16 A). A circuit target above 16 A proves that no temporary transition cap is active without hard-coding the household baseline. Charging state, pause state, phase alignment, PV export, current target and a timed quiescence window are not deployment prerequisites. The helper verifies the exact installed HomeyScript source, triggers it once, and rolls back only on source/deployment validation failure; a runtime actuator `FAILED` result remains a runtime diagnosis and does not revert a successfully installed source. Production EV writer is v0.4.4. Opportunistic charging is explicitly an offer contract: EMS exposes phase/current/session availability through Easee; Tesla consumption is not controlled by EMS and is not a success condition. Zero Tesla draw is healthy and must not create a timeout, retry or fail-closed event.

Live 3P→1P validation on 2026-09-27 exposed a separate false pause-timeout boundary: the native Easee pause command completed physically, but Homey only exposed the final `plugged_in_paused / 0 A / 0 W` state at the edge of the existing 6 s bounded polling window. The writer therefore recorded `PAUSE_CONFIRM_TIMEOUT` even though the required safe paused state was already present immediately afterwards. v0.4.4 keeps the 6 s bounded polling window unchanged, then performs exactly one final hardware read before declaring that timeout. If that read satisfies the existing strict paused predicate, the transaction continues; otherwise fail-closed behavior is unchanged. This does not extend the polling loop, weaken pause criteria, alter the 5 s phase deadtime, or change planner/P1/phase authority.


## 12. Battery boundary

The planned battery architecture is Victron AC-coupled. When commissioned, Victron/DESS remains the primary realtime battery optimizer. Pi/Homey may provide forecasts, load intent and policy constraints but must not create a competing realtime battery optimizer.

## 13. Known technical debt / next validation

- The hardened planner still contains historical compatibility code in `deadline_requirement()` with local `max_a = 16`; current authority uses runtime `deadline_max_a`.
- WW ownership remains more distributed than EV ownership because Homey still carries substantial realtime WW state/safety policy.
- PV forecast quality remains a follow-up item.
- Planner schema V0.3 does not yet embed Homey `state_revision` / `source_sample_at` in the final decision output.
- Constrained Replay V0.1.1 is runtime validated read-only EV-only analysis. The 2026-10-04 replay produced 6.8958 kWh observed export with 5.1359 kWh constraint-driven, 1.3829 kWh EV-unavoidable, 0.2200 kWh real-missed and 0.0000 kWh insufficient evidence; bounded additional feasible capture was 0.1887 kWh. Bounded AI-evidence integration is the current candidate next step.
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

The 2026-09-27 opportunity-only EV cutover exposed a stale/invalid Easee access token during a 1P→3P phase command. The v0.4.4 writer added exactly one forced Easee token refresh and one retry on HTTP 401 for the phase-command/phase-observation REST boundary. Live validation on 2026-10-02 then proved that this recovery itself can fail when the separately provisioned Easee refresh session is no longer valid: Pi realtime opportunity, Homey Bridge, EV Adapter and EV Gate were all healthy (`PASS`, 1P request), while the actuator failed closed on `EASEE_HTTP_401` and the Tesla remained paused.

EV writer v0.4.5 makes that boundary explicit. Cloud HTTP failures are operation-qualified (`EASEE_REFRESH_HTTP_*`, `EASEE_PHASE_COMMAND_HTTP_*`, `EASEE_PHASE_COMMAND_RETRY_HTTP_*`, and equivalent observation codes). A recoverable first phase-command HTTP 401 remains silent if the single refresh + retry succeeds. Terminal authentication failures such as refresh 400/401/403, missing/invalid token pair, primary phase 403, or a 401/403 on the post-refresh retry remain fail-closed and additionally emit one deduplicated operational alert for the active incident. Alert delivery is best-effort: push to the Homey Owner is preferred; if push cannot be delivered, a Homey Timeline notification is attempted. Alert delivery never changes Gate authority, never resumes charging, never bypasses `safeAbort`, and contains no token, user ID or other secret material. The remediation is re-running the private Pi commissioning bootstrap `services/pi/commissioning/bootstrap_easee_homey_tokens.py`.


## Constrained Replay -> AI bounded evidence candidate

The current candidate adds `constrainedReplay` to AI V0.4 evidence for EV,
PV/Flex or generic performance questions. The AI service invokes only the
read-only `ems-constrained-replay` command, validates schema
`EMS_PI_CONSTRAINED_REPLAY_V0.1.1`, keeps day totals, and projects at most
12 bounded windows. Explicit/context clock-time questions receive only replay
windows around the selected time. The system prompt forbids model-side
reclassification or inflation of bounded feasible capture. Replay remains
outside planner/Gate/actuator authority.

## EV energy accounting semantics

EV energy evidence distinguishes measured authority from analysis
derivations. `metrics.tesla_kwh` in the day-performance report remains a
`DERIVED_POWER_INTEGRAL` of sampled Tesla power. Combined-flex PV/grid capture
metrics remain `DERIVED_ALLOCATION`. The canonical Homey → Pi state archive now
persists Tesla/Easee `meter_kwh` as cumulative `energy_delivered_kwh` in
`ems-history.sqlite`. `ems-performance` exposes its bounded day-boundary delta
as `evEnergyAccounting.authoritativeChargedEnergy` only when cumulative-meter
coverage is complete enough for that interval; otherwise the authoritative
charged-kWh value remains unavailable rather than falling back to the sampled
power integral. EV PV/grid coverage is exposed separately as
`derivedSourceAllocation` and remains an **Afleiding**, never a directly
metered source-energy fact. This changes evidence/accounting semantics only:
EV planning, Gate, actuator, Homey control and Constrained Replay V0.1.1 are
unchanged.

## Read-only AI analysis layer — V0.4

The Pi exposes an optional read-only EMS AI analysis service for human-facing
diagnosis through Frontend V2. Canonical source is
`services/pi/api/analysis/server.py`; managed runtime is
`/home/jeroen/ems/runtime/analysis-api/`.

This service is **outside the realtime control direction**. It has no Homey,
Easee, Tesla, boiler, Honeywell or other physical-write client and does not call
the Pi control endpoint. Model output is explanatory only and is never converted
into an EMS command.

V0.2 retains the V0.1 performance and 5-minute P1/PV/Tesla-power evidence and
adds two historical EV evidence paths:

1. the existing canonical Homey -> Pi state push now archives EV connected /
   charging state, requested/offered current, measured phase currents, charge
   state, deadline context and EMS manager decision/reason/priority into
   `ems-history.sqlite`;
2. a dedicated control-neutral Homey observability push, sourced from existing
   Power Intent / Adapter / Gate / Actuator Status / Device Health Logic
   contracts, posts to `POST /state/ev-control` and archives
   `ev_control_events` locally.

The Homey EV evidence push is canonical new Homey source under
`apps/homey/observability/ev/`. It uses targeted Logic reads only: no device
reads, Logic writes, device writes or planning decisions. The Pi HTTP route
remains in `services/pi/api/status/server.py`; Homey-specific validation and
archive semantics live under
`services/pi/integrations/homey/ingress/ev_control_ingest.py`. GitHub is not
a runtime evidence transport.

The event archive records Gate result/errors, actuator status/reason, target
current/phase, confirmed phase, transition stage/failure, charge-state/device
health context and whether a physical write was reported. The full normalized
Homey evidence payload is also retained in `raw_json`. The AI reader projects
from that stored payload only the bounded realtime decision context needed for
historical EV diagnosis: Power Intent reason/source plus `phaseReason`,
`currentReason`, available total power, 2-minute rolling available power,
rolling readiness and coverage. These are recorded control reasons, not model
inference. This evidence is analysis-only and must never become an upstream
input to planner, Power Intent, Adapter, Gate or Actuator.

Repeated transport triggers with unchanged runtime evidence are deduplicated
semantically. The event hash is built from the normalized evidence fields that
are persisted, rather than from the raw transport payload. This excludes both
top-level and nested volatile timestamps such as `generatedAt`, `updatedAt`
and `sampledAt` from dedupe identity, while any actual change in Gate,
Actuator, transition, charge-state or device-health evidence remains a distinct
historical event.
 The ingest also compares each incoming normalized snapshot with the
latest persisted normalized event before relying on hash uniqueness. This keeps
dedupe correct across hash-algorithm upgrades without rewriting historical rows.

Pi operational health becomes a separate reusable read-only capability under
`services/pi/health/ems_health.py`, installed as `/usr/local/bin/ems-health`.
Schema `EMS_PI_HEALTH_V0.1` reports SYSTEM, EMS DATA, EMS FUNCTIONS and RECENT
INCIDENT SIGNALS, with overall state `HEALTHY`,
`HEALTHY_WITH_RECENT_INCIDENTS` or `DEGRADED`. Data freshness and expected
active service state are explicit. Timer-driven functions must report both an
active timer and the last triggered `.service` execution/result; an active
timer by itself is not functional-health proof. Recent incidents are a best-effort
24-hour journal view, not yet durable incident history. The collector includes
both warnings attributed directly to `ems-*` units and systemd-manager failure
messages that explicitly name an `ems-*.service` or `ems-*.timer`. Duplicate
systemd failure messages for the same unit within 10 seconds are collapsed.
A recovered recent incident therefore yields `HEALTHY_WITH_RECENT_INCIDENTS`
when current data/functions are healthy; current degradation always remains
`DEGRADED`. Current health may provide context but is not proof of health at a
historical decision timestamp.

Richer EV telemetry and event history exists only from V0.2 commissioning
forward. Missing earlier evidence must remain missing; it must not be backfilled
by inference.

V0.3 broadens the same read-only analysis boundary without adding any control
authority. The bounded 5-minute evidence timeline now includes boiler and Quatt
power plus washer/dryer active state where canonical history exists. For
question-relevant timestamps, the AI reader selects the latest frozen
`planner-history.sqlite` decision snapshot generated at or before the anchor
and projects only the relevant canonical planner slot, allocation targets and reasons. It also compares archived
PV forecast with canonical 15-minute actuals using the fixed 12-hour
no-hindsight forecast selection already used by PV & Flex. Later forecasts may
not be used to explain or judge earlier planner decisions.

The added planner and forecast readers remain SQLite `mode=ro` with
`PRAGMA query_only=ON`, feed model context only, and are never consumed
upstream by planner, Gate, actuator or any device writer.

V0.4 adds two retrospective evidence paths without changing control ownership.
A Pi-local timer archives bounded Heating Preheat V0.3 eligibility/CV guards,
Flex Priority V0.1 decisions, Heating Preheat V0.4 progression SHADOW state and
WW input/source/advice into
`planner-history.sqlite/flex_context_snapshots`. The archive is semantic,
deduplicated and read-only with respect to EMS control; it consumes only already
derived local artifacts and performs no Homey, network or device calls.

Quooker remains deliberately outside the canonical Core snapshot. A dedicated
Homey observability push under `apps/homey/observability/quooker/` reads only
the existing Quooker Control, SHADOW Actuator Status and detector-diagnostic
Logic contracts and posts authenticated evidence to `POST /state/quooker`.
The Pi persists normalized events in
`ems-history.sqlite/quooker_control_events`. The transport performs no device
reads or Logic/device writes and does not make planning decisions.

Heating progression and the current Quooker actuator are SHADOW. AI evidence
must therefore keep eligibility, planner grant, desired/would-write state and
measured physical behavior separate. A `SHADOW_GRANT`, `desiredOn` or
`wouldWrite` value is not proof that a device command occurred. Historical
Heating/WW and Quooker coverage begins only at V0.4 commissioning; earlier
missing evidence is never reconstructed from present state.

V0.4.1 hardens evidence interpretation without changing control ownership.
For an in-progress day, `ems-performance` now distinguishes calendar-day
progress from completeness of the elapsed measurement interval:
`dayProgressPct`, `coveragePctFullDay`, `coveragePctElapsed` and
`elapsedCoverageStatus`. The existing `PARTIAL_TODAY` state means the day is
not complete; it must not by itself be interpreted as missing measurements.

The AI evidence layer also adds explicit EV `deadlineSemantics` at each
historical reference time. Old `deadlineAt` and `remainingKWh` values remain
available for audit, but only evidence with
`deadlineSemantics.effective=true` may be treated as an active deadline
constraint. This is analysis-only normalization; the canonical EV deadline
state machine, planner constraint logic, Homey executor and physical control
paths are unchanged.

Semantic Event History V0.1 adds durable, sparse state-change evidence
without adding control authority. A Pi-local observer at `:50` reads only
already-derived local artifacts and stores transitions in
`ems-history.sqlite/semantic_events`. Initial observations establish a
baseline only; no event is invented at commissioning and no earlier state is
backfilled.

The first bounded event classes are EV connect/charge transitions, EV deadline
command and deadline-state transitions, warm-water source-mode changes, Flex
Priority changes and per-room Heating SHADOW progression changes. Warm-water
source state is normalized at the semantic boundary from the canonical Homey
boolean contract (`false = CV`, `true = BOILER`) to explicit `CV` /
`BOILER` values. A pre-normalization boolean baseline is upgraded in place;
that representation-only migration must not create a synthetic
`WW_SOURCE_CHANGED` event.

Every event carries explicit provenance:
`USER_INTENT_COMMAND`, `OBSERVED_STATE`, `DERIVED_STATE` or
`SHADOW_DECISION`. A user-intent command is not proof of physical execution,
an observed state change does not identify its actor, and a SHADOW decision is
never a physical write. The AI exposes the commissioning boundary separately as
`semanticEventCoverage`.

The semantic observer contains no Homey/network client, creates no planner
decision and performs no Logic/device/control writes. Realtime planner, Gate,
actuator and physical-control ownership remain unchanged. `ems-health`
monitors the semantic-event timer and its last oneshot execution.

For latest/current EV-deadline questions, the AI evidence package also reads
the canonical Pi runtime command
`/home/jeroen/ems/data/tesla-deadline-command.json` directly as
`currentDeadlineCommand`. This is the authority for the currently accepted
user-intent command and is explicitly separate from Homey executor/realtime
`evControlEvents`. Executor targets such as W/A/phase mode are never promoted
to a user deadline command. Historical deadline changes remain sourced from
`semanticEvents`; the current command is not projected backwards into earlier
times or non-current days. This direct read is analysis-only and adds no write,
planner or control authority.

The current V0.4 evidence-quality semantics also require directly observed
appliance state in `timeline5m` to be used when relevant to a power-event
question. For example, `washerActive=true` is a recorded **Feit** that must
not be omitted when it is relevant to explaining a household power event.
Relevance is now explicit: unrelated device-state observations must not be
included merely because they are present in the evidence. In a Tesla-specific
status question, washer/dryer state is omitted unless it materially explains or
constrains the Tesla event. Device-active state remains distinct from power
attribution: without separate measured washer power, the AI may identify the
active washer as a supported possible explanation but must not claim that it
caused the measured P1 change.

For questions containing explicit local clock times, V0.4 applies
question-aware evidence selection to the large day-wide arrays:
`timeline5m`, `evTelemetry5m`, `evControlEvents`, `quookerEvents`
and `semanticEvents`. Only points within ±30 minutes of the explicit user
times are transported to the model. A referential follow-up such as "dit tijdslot" may resolve one of
those windows from the bounded recent conversation context and is then marked
`CONTEXT_TIME_WINDOW`. Topic filtering now runs after either explicit or
contextual time scoping, so the window determines *when* while the detected
topic set determines *which subsystem streams* remain. A PV/Flex-only time
window therefore does not retain unrelated EV or Quooker evidence.

Without an explicit/contextual time anchor, day-scope evidence is now bounded
and topic-aware instead of transporting every available event. Event streams
are compacted deterministically; unrelated EV or Quooker streams are omitted
for topic-specific questions. `evidenceSelection` records the mode, topics,
context-anchor use, compacted/omitted fields and original/selected counts. The
browser supplies at most four recent non-error messages (1200 characters each)
as referential context only; prior chat text is not EMS evidence.

A final pre-flight input budget now protects the model boundary. The service
targets 80,000 estimated input tokens and fails closed above 100,000 estimated
tokens after deterministic budget compaction. The estimate is intentionally
conservative and uses UTF-8 bytes / 2.5 rather than introducing a tokenizer
runtime dependency; `exactTokenizer=false` is exposed with the budget
metadata. If the target is exceeded, already-selected event/window collections
are reduced in documented steps and `budgetCompactedFields` records what was
reduced. If the hard limit still cannot be met,
`MODEL_INPUT_BUDGET_EXCEEDED` is returned before any OpenAI request. This
limits oversized single requests but does not replace provider rolling
rate-limit handling. Canonical history, source authority, polling, planner,
Homey and physical-control paths are unchanged.

Frontend V2 exposes the human interface at `/ai/`. Private Caddy ingress
proxies `/agent/*` only to the loopback analysis service. Model credentials
remain host-local under `/etc/ems/ai-agent.env` and must never be committed.
Missing credentials fail explicitly rather than degrading to fabricated
analysis.

AI model-response handling now preserves the distinction between an actually
empty completed response and other non-text Responses API outcomes. Incomplete
responses caused by the configured output budget are reported as
`MODEL_INCOMPLETE_MAX_OUTPUT_TOKENS`; refusal, content-filter and explicit
response-error paths remain separately identifiable. A bounded journal event
records only model response ID, response status/reason and aggregate token
counts. It never records the question, EMS evidence, model/refusal text or
credentials. No automatic retry or output-budget increase is part of this
observability hardening. The deployed AI service now runs with
`EMS_AI_REASONING_EFFORT=medium` and retains the 4096-token ceiling. This
follows a measured successful 2026-10-04 request of about 198 seconds
end-to-end while the same evidence build completed in about 0.68 seconds.

Successful model responses additionally emit a bounded journal record with
response ID, model-call duration and aggregate token counts. A locally active
request ID remains PENDING regardless of the 180-second stale threshold, so a
long-running valid model request cannot be reclaimed into a duplicate call.
Only an old PENDING row with no active owner in the current service process may
become STALE/reclaimable, preserving restart/crash recovery.

V2 AI navigation is resumable. The browser keeps the visible conversation in
tab-scoped `sessionStorage` and attaches a generated `requestId` to an
analysis request. New requests also carry a bounded four-message recent
conversation context for referent resolution; model/API error messages are
excluded and the current request is not duplicated in that context. The Pi
persists only the corresponding short-lived UI job/result in
`/home/jeroen/ems/data/ai-analysis-jobs.sqlite` (24-hour retention). `GET /agent/result?requestId=...` lets the browser recover an
answer after navigating to another V2 page and returning. Duplicate POSTs with
the same ID are idempotent and therefore do not create a second OpenAI model
call while a job is pending or after it has completed.

This UI job cache is not EMS history, planner state or control state and is
never an input to realtime control. The analysis service remains read-only
toward EMS state and physical devices; its only mutable state is this bounded
human-interface result cache.

The AI evidence path preserves read-only query semantics. `ems-performance`
and the AI timeline/event readers open live SQLite with `mode=ro` and
`PRAGMA query_only=ON`. Because `ems-history.sqlite` runs in WAL mode, the
hardened AI systemd sandbox grants the bounded filesystem carve-out
`ReadWritePaths=/home/jeroen/ems/data` for WAL/SHM coordination. This does not
make the SQL connections writable. `immutable=1` is forbidden for AI reads of
the live operational history.
