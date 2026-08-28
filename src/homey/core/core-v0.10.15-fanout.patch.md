# Core v0.10.15 fan-out patch

Baseline: `core-v0.10.14.js`.

Goal: suppress Homey Logic updates that differ only by transport/freshness timestamps while preserving all existing Core calculations and state machines.

## Intended code change

Add a semantic normalizer immediately before `set()` and replace the v0.10.14 exact-equality-only `set()` implementation.

```js
const SEMANTIC_JSON_VARS=new Set([
  'EM2_State',
  'EM2_Decision',
  'EM2_Shadow',
  'EM2_WW_State',
  'EM2_Control_WW',
  'EM2_Public_State',
  'EM2_Publisher_Status'
]);
const VOLATILE_KEYS=new Set([
  'sampledAt','changedAt','publishedAt','ts','updatedAt','generatedAt','heartbeat_at',
  'generated_at','source_sample_at','state_age_sec','stateAgeSec','lastStateSampleAt','at',
  'p1AgeSec','ageSec','maxAgeSec','skewSec'
]);
const semanticValue=value=>{
  const walk=v=>{
    if(Array.isArray(v)) return v.map(walk);
    if(v&&typeof v==='object'){
      const out={};
      for(const k of Object.keys(v).sort()){
        if(VOLATILE_KEYS.has(k)) continue;
        out[k]=walk(v[k]);
      }
      return out;
    }
    return v;
  };
  try{return JSON.stringify(walk(JSON.parse(String(value))));}
  catch{return String(value);}
};
const set=async(name,type,value)=>{
  const v=byName[name];
  if(v){
    if(v.value===value)return v;
    if(type==='string'&&SEMANTIC_JSON_VARS.has(name)&&semanticValue(v.value)===semanticValue(value))return v;
    await Homey.logic.updateVariable({id:v.id,variable:{value}});
    v.value=value;
    return v;
  }
  const nv=await Homey.logic.createVariable({variable:{name,type,value}});
  byName[name]=nv;
  return nv;
};
```

## Safety constraints

- No device writes added.
- No existing Tesla, Equalizer, Quatt, Quooker, washer/dryer or warm-water logic removed or reordered.
- `EM2_Publish_Due` remains the v0.10.14 single boolean write path; do not restore the old forced trailing `true`.
- Core remains disabled during deployment and initial validation.
- Power Intent/downstream stays disabled for the first Core smoke.

## Important follow-up

This generic normalizer is stage 1. `EM2_Public_State` must subsequently be removed as an internal control trigger and downstream Power Intent should react to semantic revision/intent instead of publication refreshes. That is a separate reviewed change after v0.10.15 validation.
