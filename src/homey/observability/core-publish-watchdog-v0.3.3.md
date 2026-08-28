# Homey runtime baseline — Core + Publish Freshness v0.3.3 staggered

Flow ID: `8526109f-5c8d-428e-ac24-85a71c95ac36`

Captured 2026-08-28. Runtime state: `enabled=false`, `broken=false`, `triggerable=false`.

Trigger: every 5 minutes, then 120-second delay.

Core freshness condition:
```js
const vars=await Homey.logic.getVariables();const v=Object.values(vars).find(x=>x.name==='EM2_State');if(!v?.value)return true;try{const s=JSON.parse(String(v.value));const t=Date.parse(s.sampledAt||'');return !Number.isFinite(t)||(Date.now()-t)>7*60*1000;}catch{return true;}
```

If true, Homey currently triggers flow ID `227f8d3b-7551-46dd-837d-1b8c69add824`, but the stored card label is stale and still says `EM v2 | 00 Core Tick | v0.10.12 (WW post-goal SHOULD)`.

Publication freshness condition:
```js
const vars=await Homey.logic.getVariables();const a=Object.values(vars);const last=a.find(x=>x.name==='EM2_Last_Publish');const due=a.find(x=>x.name==='EM2_Publish_Due');const t=Date.parse(String(last?.value||''));const stale=!Number.isFinite(t)||(Date.now()-t)>7*60*1000;return stale||due?.value===true||String(due?.value).toLowerCase()==='true';
```

If true, Homey currently triggers flow ID `fe84bc17-72d4-4fbb-9a69-b3d751b0ffcd`, but the stored card label is stale and still says `EM v2 | 04 Publisher | v1.0.4 (Tesla lifecycle)`.

Important capture finding: both repair target IDs still point to the current Core/Publisher flow IDs, but the embedded labels are obsolete. The watchdog also performs two separate broad `Homey.logic.getVariables()` scans per run when both conditions are evaluated.
