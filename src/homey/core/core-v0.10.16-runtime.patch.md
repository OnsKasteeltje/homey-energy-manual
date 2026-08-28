# Core v0.10.16 runtime reconstruction patch

Status: **CAPTURED FROM ACTIVE HOMEY RUNTIME**

Homey Advanced Flow: `EM v2 | 00 Core Tick | v0.10.16 (safe semantic fan-out)`  
Flow ID: `227f8d3b-7551-46dd-837d-1b8c69add824`

Reconstruction baseline: `core-v0.10.14.js`.

The active Homey runtime identifies itself as:

```js
// EM v2 | 00 Core Tick | v0.10.16 — safe semantic Logic fan-out suppression
const PUB_VERSION='EM2_CORE_STATE_V0.10.16';
```

All v0.10.14 functional calculations/state machines are retained. Replace the original v0.10.14 `set()` helper with the following exact v0.10.16 runtime block:

```js
const SEMANTIC_JSON_VARS=new Set(['EM2_State','EM2_Decision','EM2_Shadow','EM2_Control_WW','EM2_Publisher_Status']);
const VOLATILE_KEYS=new Set(['sampledAt','changedAt','publishedAt','ts','updatedAt','updated_at','generatedAt','generated_at','heartbeat_at','source_sample_at','state_age_sec','stateAgeSec','lastStateSampleAt','at','p1AgeSec','ageSec','age_sec','maxAgeSec','skewSec','lastSample','last_sample_at','sources']);
const semanticValue=value=>{const walk=v=>{if(Array.isArray(v))return v.map(walk);if(v&&typeof v==='object'){const out={};for(const k of Object.keys(v).sort()){if(VOLATILE_KEYS.has(k))continue;out[k]=walk(v[k]);}return out;}return v;};try{return JSON.stringify(walk(JSON.parse(String(value))));}catch{return String(value);}};
const set=async(name,type,value)=>{const v=byName[name];if(v){if(v.value===value)return v;if(type==='string'&&SEMANTIC_JSON_VARS.has(name)&&semanticValue(v.value)===semanticValue(value))return v;await Homey.logic.updateVariable({id:v.id,variable:{value}});v.value=value;return v;}const nv=await Homey.logic.createVariable({variable:{name,type,value}});byName[name]=nv;return nv;};
```

Important v0.10.16 correction versus the earlier generic v0.10.15 patch:

- `EM2_WW_State` is deliberately **not** in `SEMANTIC_JSON_VARS`, because its cadence/time accounting must persist.
- `EM2_Public_State` is deliberately **not** in `SEMANTIC_JSON_VARS`, because publication heartbeat/freshness must continue to advance.
- Internal semantic outputs remain suppressed when only volatile timestamp/freshness metadata changes.
- `EM2_Publish_Due` remains the single boolean publication-due path.
- No physical device writes are introduced; Core remains SHADOW/read-only.

The active Homey note states:

> v0.10.16 — exact v0.10.15 functional logic retained. EM2_WW_State cadence persistence and EM2_Public_State heartbeat are no longer semantic-suppressed; internal state/control outputs remain semantically suppressed. PURE SHADOW.

## Migration gate

This runtime-sync change-set must receive one targeted Core-chain smoke PASS before any Planner-input modification is layered on top.
