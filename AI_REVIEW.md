# AI Review Standard

This file defines the vendor-neutral review contract for independent AI review of the Home Energy Management System repository.

The purpose is not to generate code. The reviewer acts as an independent auditor and must challenge assumptions, find inconsistencies, and determine whether the current implementation is suitable as a Release Candidate.

## 1. Review objective

Review the complete repository as one integrated system. Do not limit the review to individual files or recent changes.

Assess whether the implementation is:

- functionally correct;
- safe for unattended home-energy control;
- deterministic and idempotent;
- resilient to restarts, stale data, duplicate triggers and transient API failures;
- conservative with Homey/Easee writes and API calls;
- consistent with the documented architecture and process flows;
- sufficiently observable and testable for Release Candidate status.

The reviewer must distinguish between:

- PRODUCTION behaviour;
- SHADOW behaviour;
- documentation-only or planned behaviour.

Never treat SHADOW or documentation-only logic as if it were active production control.

## 2. Evidence rules

Every finding must contain evidence.

Acceptable evidence includes:

- exact file path;
- function, class, flow or variable name;
- relevant code/configuration fragment;
- test name and result;
- runtime log/history evidence;
- commit or PR reference when relevant.

Do not give PASS based only on intent, comments, documentation, naming or architectural diagrams.

If implementation evidence is unavailable, report `NOT PROVEN` rather than PASS.

If documentation contradicts code, code describes current runtime behaviour and the inconsistency must be reported separately.

## 3. Severity

Classify each finding as:

- **CRITICAL** — risk of unsafe physical control, uncontrolled charging/heating, corrupted control state, or major security exposure.
- **HIGH** — likely incorrect EMS behaviour, duplicate physical actions, invalid policy selection, broken restart recovery, or substantial regression risk.
- **MEDIUM** — meaningful correctness, observability, maintainability or resilience problem without immediate unsafe behaviour.
- **LOW** — localized quality, clarity or maintainability issue.
- **INFO** — relevant observation that does not require remediation for RC.

Also mark whether the finding is an **RC BLOCKER**.

## 4. Mandatory review areas

### 4.1 Architecture and control boundaries

Verify that control responsibilities are clearly separated and that lower-level device writes cannot bypass central EMS policy unintentionally.

Check for:

- duplicated decision logic in multiple flows/modules;
- hidden or legacy control paths;
- dead code that can still be triggered;
- conflicting schedulers/timers;
- control logic embedded in UI or documentation tooling;
- failure to distinguish observations, recommendations and physical actions.

### 4.2 Contract-aware energy policy

Verify correct separation of FIXED and DYNAMIC electricity contract behaviour.

Specifically inspect for legacy price signals such as `M7_Price_*` or equivalent price classifications that could influence production behaviour while contract type is FIXED.

Confirm that:

- contract type has one authoritative source;
- policy selection is explicit;
- FIXED mode cannot accidentally execute dynamic-price decisions;
- DYNAMIC-only signals are either gated or ignored in FIXED mode;
- SHADOW experiments cannot alter production control.

### 4.3 Tesla / Easee charging lifecycle

Review the complete EV lifecycle from plug-in to stop/restore.

Check:

- behaviour immediately after the Tesla is plugged in;
- opportunity charging;
- deadline charging;
- target SOC handling;
- transition back from deadline mode to normal policy;
- charger current limits;
- pause/resume/stop semantics;
- restart recovery;
- stale deadline protection;
- deadlines in the past;
- lifecycle state persistence;
- Tesla/Easee state disagreement;
- physical-write deduplication.

Explicitly determine whether two nearly simultaneous controller starts can result in more than one physical Easee action.

Review any run lease, lock or equivalent mechanism and verify that it protects the complete critical section rather than only part of the execution.

### 4.4 Easee write minimization

Treat unnecessary charger writes as a reliability concern.

Identify:

- repeated writes of an unchanged value;
- periodic reassertion of state without need;
- enable/disable charger commands when pause/current-limit semantics are sufficient;
- retries without deduplication;
- loops or flows capable of rapid repeated writes.

The preferred behaviour is no physical write when the desired state already equals the effective device state.

### 4.5 Idempotency and concurrency

For every externally triggered or scheduled control path, determine what happens when it runs twice nearly simultaneously.

Verify:

- at most one physical action;
- at most one notification;
- at most one history/audit record when semantically one event occurred;
- no duplicated state transitions;
- safe retries after partial failure.

Pay particular attention to controller ticks, flow starts, deadline commands and restart recovery.

### 4.6 Restart and recovery

Review behaviour after:

- Homey reboot;
- app/process restart;
- controller restart during an active action;
- temporary device/API unavailability.

Verify automatic recovery of authoritative state including, where applicable:

- contract type;
- hot-water/boiler mode;
- Tesla lifecycle state;
- active charging mode/deadline state;
- notification deduplication state;
- run leases/locks;
- persisted control metadata.

Flag any state that requires manual repair after restart.

### 4.7 Boiler / hot-water control

Review the full boiler state machine and all entry/exit paths.

Check that states such as heating, cooling/waiting and temperature-satisfied cannot become contradictory or stuck.

Verify:

- minimum required heating duration or deadline behaviour where configured;
- production versus SHADOW boundaries;
- safe handling of missing/stale measurements;
- manual mode switches;
- restart recovery;
- no simultaneous conflicting ON/OFF paths.

### 4.8 Measurement freshness and derived power

Review all decisions that combine measurements with different timestamps or refresh rates.

Check for:

- stale PV data combined with fresh P1 data;
- negative or impossible derived house load;
- missing-device values treated as zero without justification;
- sign-convention mistakes between import/export and production/consumption;
- decisions made without explicit freshness validation.

Derived values must document their formula and freshness assumptions.

### 4.9 Appliance fingerprinting

Fingerprint recognition must remain observational unless explicitly approved for control.

Verify:

- fingerprints cannot accidentally trigger unsafe physical actions;
- residual `Other` consumption is mathematically consistent;
- overlapping fingerprints do not double-count consumption;
- confidence/ambiguity is handled explicitly;
- ground-truth samples are distinguishable from inferred detections.

### 4.10 Homey/API rate limits

Review all polling, scheduled flows, retries and API operations for rate-limit risk.

Identify:

- redundant reads;
- unnecessarily frequent polling;
- multiple collectors requesting the same data;
- retry storms;
- failure behaviour when throttled.

The system must degrade safely when data retrieval is delayed.

### 4.11 Website and telemetry

Verify that the website is an observer of system state and does not become an accidental control source unless explicitly designed as such.

Check:

- live values and timestamps;
- stale-data indication;
- household energy-balance calculations;
- Tesla/boiler/space-heating attribution;
- `Other` as residual after identified consumers;
- UI state versus actual production state;
- cache/refresh behaviour;
- distinction between measured and inferred data.

### 4.12 Security and secrets

Search the repository for:

- credentials;
- tokens;
- API keys;
- private URLs containing secrets;
- personal information that should not be committed;
- excessive permissions.

Any active secret committed to the repository is at least HIGH severity and normally an RC blocker until revoked/rotated and removed appropriately.

### 4.13 Documentation versus implementation

Process-flow diagrams and software architecture documentation must describe the currently coded behaviour.

Compare documentation with code and report:

- undocumented production behaviour;
- documented behaviour not implemented;
- renamed/obsolete states or variables;
- flow diagrams that no longer match execution order;
- SHADOW functionality presented as production.

Documentation mismatch is never grounds to reinterpret the code; it is a separate defect.

### 4.14 Testing and observability

Determine whether failures can be diagnosed after the fact.

Review:

- unit/integration/runtime tests;
- deterministic testability of decision logic;
- structured logging;
- physical-write audit history;
- reason codes for decisions;
- error handling;
- test coverage of failure and concurrency paths.

For critical actions, the audit trail should make it possible to answer: what was decided, why, which input values were used, whether a physical command was sent, and what the observed result was.

## 5. Required adversarial scenarios

Explicitly reason through at least these scenarios:

1. Two Core/controller ticks start nearly simultaneously.
2. Two deadline-charge commands are submitted close together.
3. Homey restarts during Tesla deadline charging.
4. Homey restarts while the boiler is active.
5. Easee accepts a command but the caller times out and retries.
6. Easee is temporarily unreachable.
7. P1 is fresh but one or more PV sources are stale.
8. Contract type is FIXED while legacy dynamic-price signals still contain valid values.
9. A stale deadline exists in the past when the Tesla is plugged in.
10. Tesla begins charging immediately on plug-in before EMS opportunity logic evaluates the situation.
11. SHADOW logic computes a physical target but must not actuate it.
12. A notification-triggering condition is evaluated twice.
13. Website/telemetry data is stale while control logic remains active.
14. A fingerprint matches while another large appliance is active simultaneously.
15. A write target already equals the effective device value.

For each scenario give one of: `PASS`, `FAIL`, or `NOT PROVEN`, with evidence.

## 6. Release Candidate gate

The reviewer must produce an explicit final RC decision.

### PASS

RC may be marked PASS only when:

- there are no open CRITICAL findings;
- there are no open HIGH RC blockers;
- duplicate/concurrent execution is proven not to cause duplicate physical actions;
- restart recovery is proven for critical persistent state;
- FIXED/DYNAMIC contract separation is proven;
- SHADOW cannot actuate production devices;
- unsafe/stale input handling is fail-safe;
- critical physical actions have sufficient auditability;
- mandatory adversarial scenarios are either PASS or have an explicitly accepted non-blocking limitation.

### FAIL

RC must be FAIL if any RC-blocking condition remains.

### NOT PROVEN

If evidence is missing for a critical RC criterion, do not infer success. Mark the criterion `NOT PROVEN` and treat it as an RC blocker unless there is a documented reason it is outside scope.

## 7. Required output format

Use this structure exactly.

### A. Executive conclusion

- Overall verdict: `PASS`, `FAIL`, or `NOT PROVEN`
- Number of CRITICAL / HIGH / MEDIUM / LOW findings
- Top three release risks

### B. RC gate matrix

| Criterion | Result | Evidence | Blocker |
|---|---|---|---|
| Architecture/control boundaries | PASS/FAIL/NOT PROVEN | ... | Yes/No |
| FIXED/DYNAMIC separation | ... | ... | ... |
| SHADOW isolation | ... | ... | ... |
| Tesla/Easee lifecycle | ... | ... | ... |
| Idempotency/concurrency | ... | ... | ... |
| Restart recovery | ... | ... | ... |
| Boiler control | ... | ... | ... |
| Measurement freshness | ... | ... | ... |
| API/write minimization | ... | ... | ... |
| Security/secrets | ... | ... | ... |
| Documentation consistency | ... | ... | ... |
| Testing/observability | ... | ... | ... |

### C. Findings

For every finding provide:

- ID, e.g. `AIR-001`;
- severity;
- RC blocker Yes/No;
- exact evidence;
- failure mechanism;
- consequence;
- smallest safe remediation;
- verification required after remediation.

### D. Adversarial scenario results

Report every scenario from section 5 individually.

### E. Unproven assumptions

List everything the reviewer could not prove from repository evidence.

### F. Recommended remediation order

Order remediation by safety and RC impact, not by implementation convenience.

### G. Final RC verdict

End with exactly one explicit statement:

`RC VERDICT: PASS`

or

`RC VERDICT: FAIL`

or

`RC VERDICT: NOT PROVEN`

## 8. Reviewer behaviour

The reviewer must be skeptical and independent.

Do not:

- assume previous reviewers were correct;
- suppress a finding because code appears intentional;
- redesign large parts of the system when a smaller safe correction exists;
- award PASS because tests exist without checking what they prove;
- treat an AI-generated comment as evidence;
- conflate website presentation with physical control state.

Prefer concrete, reproducible defects over stylistic opinions.

When uncertain, state what evidence would resolve the uncertainty.

---

## Ready-to-use review prompt

Use the following instruction with Gemini, Claude, Copilot, ChatGPT or another capable code-review model:

> Read `AI_REVIEW.md` first and treat it as the governing review contract. Independently audit the complete repository against every mandatory area and adversarial scenario. Do not modify code during the first pass. Cite exact repository evidence for every PASS and every finding. If evidence is missing, use NOT PROVEN. Produce the required output format and finish with the explicit RC verdict.