// Runtime capture 2026-08-30
// Flow ID: 8526109f-5c8d-428e-ac24-85a71c95ac36
// Homey runtime enabled=false, broken=false; every 5 min + 120 s delay.
// NOTE: Homey card display names/notes still reference old Core v0.10.12 and Publisher v1.0.4 names, while their flow IDs resolve to the current Core/Publisher IDs. Captured as-is.
async function coreFreshnessCondition(){
  const vars=await Homey.logic.getVariables();const v=Object.values(vars).find(x=>x.name==='EM2_State');if(!v?.value)return true;try{const s=JSON.parse(String(v.value));const t=Date.parse(s.sampledAt||'');return !Number.isFinite(t)||(Date.now()-t)>7*60*1000;}catch{return true;}
}
async function publicationFreshnessCondition(){
  const vars=await Homey.logic.getVariables();const a=Object.values(vars);const last=a.find(x=>x.name==='EM2_Last_Publish');const due=a.find(x=>x.name==='EM2_Publish_Due');const t=Date.parse(String(last?.value||''));const stale=!Number.isFinite(t)||(Date.now()-t)>7*60*1000;return stale||due?.value===true||String(due?.value).toLowerCase()==='true';
}
// If coreFreshnessCondition() is true, Homey programmatically triggers flow ID
// 227f8d3b-7551-46dd-837d-1b8c69add824 (current Core runtime ID).
// If publicationFreshnessCondition() is true, Homey programmatically triggers flow ID
// fe84bc17-72d4-4fbb-9a69-b3d751b0ffcd (current Publisher runtime ID).
