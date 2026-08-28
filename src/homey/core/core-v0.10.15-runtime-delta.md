# Core v0.10.15 runtime delta

Runtime flow: `227f8d3b-7551-46dd-837d-1b8c69add824`
Runtime name: `EM v2 | 00 Core Tick | v0.10.15 (semantic fan-out)`
Deployment state: disabled / SHADOW / broken=false.

The Homey runtime is the generated `core-v0.10.15.js` candidate with one deliberate safety correction to the semantic normalization guard. No Tesla, WW, Quatt, Quooker, laundry, balance, cadence, reader, or actuator logic was changed.

Runtime `VOLATILE_KEYS`:

```js
const VOLATILE_KEYS=new Set(['sampledAt','changedAt','publishedAt','ts','updatedAt','updated_at','generatedAt','generated_at','heartbeat_at','source_sample_at','state_age_sec','stateAgeSec','lastStateSampleAt','at','p1AgeSec','ageSec','age_sec','maxAgeSec','skewSec','lastSample','last_sample_at','sources']);
```

Compared with the initially generated candidate, the runtime additionally treats `updated_at`, `age_sec`, `lastSample`, `last_sample_at`, and `sources` as transport/freshness metadata. The `sources` map only contains source sample timestamps; semantic freshness/synchronization flags remain outside that map and therefore remain part of the semantic comparison.

This delta exists because connector-created commits did not trigger the deterministic GitHub Actions regeneration. Before promoting v0.10.15 as the repository baseline, regenerate or replace `core-v0.10.15.js` so it matches this runtime line exactly, then remove this temporary delta note.

Stage 2 remains open: decouple `EM2_Public_State` publication/heartbeat changes from the internal Power Intent trigger path.
