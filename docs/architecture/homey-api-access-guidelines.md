# Homey API Access Guidelines — Mandatory Low-Load Rules

Status: **MANDATORY / NON-NEGOTIABLE**

Date: 2026-08-30

## Purpose

Homey API capacity is a scarce system resource. Development, diagnostics and maintenance calls can themselves contribute to `429 Too many requests` and must therefore follow the same low-load architecture principles as the EMS runtime.

These rules apply to **all** manual, assistant-driven, diagnostic, development, deployment and maintenance interaction with Homey.

## Non-negotiable rules

1. **Never rediscover known stable IDs.**
   - Reuse stable Homey device, Flow and Logic variable IDs from the project/runtime registry.
   - Discovery/autocomplete is allowed only for a genuinely new or unverified object.

2. **Current-state verification must be targeted.**
   - Before changing a Flow, read that specific Flow once when current runtime state matters.
   - Do not perform broad inventory scans merely to reconfirm already-known configuration.

3. **No serial discovery bursts.**
   - Never validate a list of known Logic variables through individual autocomplete/API calls in rapid succession.
   - A large set of small requests is still a burst and is considered unsafe.

4. **Minimize the number of calls per change.**
   - Preferred pattern: one targeted pre-change read, the minimum required write, and one targeted post-change verification read.
   - Additional calls require a concrete reason relevant to safety or correctness.

5. **No retry after rate limiting.**
   - On `429 Too many requests`, stop all non-essential Homey interaction immediately.
   - Do not retry, probe repeatedly, or switch to another Homey endpoint as a workaround.
   - Resume only in a later controlled interaction after a cooling-off period.

6. **No broad reads when a targeted read is available.**
   - Avoid `getDevices()`, `getVariables()` and equivalent full-collection reads in normal runtime and development procedures unless a one-off inventory operation is explicitly required.

7. **Batch work outside Homey.**
   - Design, code generation, diffing, dependency analysis and ID mapping should be done from the GitHub/source registry wherever possible.
   - Homey is the runtime authority for current state, not the primary development database.

8. **Separate observation from mutation.**
   - Do not combine exploratory discovery, smoke testing and production writes in one uncontrolled call sequence.
   - Establish current state first, prepare the complete change outside Homey, then perform the smallest controlled mutation sequence.

9. **Do not use physical device writes for validation unless explicitly required.**
   - Prefer SHADOW/read-only validation.
   - Physical writes require the applicable Gate/safety conditions and an explicitly agreed test.

10. **429 prevention is an acceptance criterion.**
    - A technically correct implementation that materially increases Homey request bursts or rate-limit frequency is not acceptable.

11. **Homey access is globally serialized across ChatGPT sessions/tabs.**
    - Treat all browser tabs, ChatGPT conversations, scheduled tasks and assistant-driven workflows as sharing one Homey API budget.
    - If one session is executing a Homey call sequence, **no second Homey call sequence may be started from another session/tab** until the first sequence is complete.
    - Do not assume separate ChatGPT chats have separate Homey rate-limit capacity.
    - Before starting a multi-call Homey operation, the active session must be considered to hold the Homey access lock for the duration of that operation.
    - When there is any uncertainty whether another session is currently using Homey, **fail closed: do not start the new Homey sequence** until the user confirms that no other Homey work is running.
    - Single diagnostic pings are also Homey calls and must respect this serialization rule.

## Default interaction budget

For a normal single-Flow modification, the default Homey interaction pattern is:

1. one targeted current-state read;
2. one minimum required write/update;
3. one targeted verification read.

This is a **guideline ceiling, not a quota to consume**. If fewer calls are sufficient, use fewer. If more calls are genuinely necessary, stop and plan the sequence first rather than issuing exploratory calls interactively.

The interaction budget applies **globally across concurrent ChatGPT sessions**, not independently per tab or conversation.

## Incident lesson — 2026-08-30

During Quooker v0.4 preparation, approximately 16 Homey calls were made in a short development window, including a burst of individual Logic autocomplete lookups. Most of those IDs were already known. Homey subsequently returned `429 Too many requests`.

Conclusion: even lightweight read-only calls can collectively form an unsafe API burst. Stable-ID reuse, request-count discipline and cross-session serialization are therefore mandatory for both runtime code and development operations.

## Relation to EMS architecture

These operational rules extend the existing v0.11b design principle that replacing one broad read with dozens of targeted requests is not an acceptable optimization. Request **count, burst shape, payload, wake-up frequency and concurrency across sessions** must all be considered together.

## Enforcement

These rules may only be deviated from when there is a concrete safety/correctness reason and the additional Homey calls are planned before execution. Convenience, repeated reassurance, parallel work from another browser tab or rediscovery of already-recorded IDs is not a valid reason.
