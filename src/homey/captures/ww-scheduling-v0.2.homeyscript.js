// Runtime capture 2026-08-30
// Flow ID: 1d822642-87e8-4b0f-870e-5f2e7eef9372
// Flow: EM v2 | 70 Planner | WW Scheduling SHADOW v0.2
// Homey runtime enabled=true, broken=false; programmatic trigger only.
// EM v2 | 70 Planner | WW Scheduling SHADOW v0.2
// Uses current Planner contract: EM2_Energy_Plan_24h. SHADOW only; no device writes.
const VAR_PLAN='EM2_Energy_Plan_24h',VAR_OUT='EM2_WW_Planner_Intent';
const vars=await Homey.logic.getVariables(), byName=n=>Object.values(vars).find(v=>v.name===n);
const pv=byName(VAR_PLAN); if(!pv)throw new Error('EM2_Energy_Plan_24h ontbreekt');
let plan; try{plan=JSON.parse(String(pv.value||''));}catch{throw new Error('Planner JSON ongeldig');}
const ww=plan?.obligations?.ww??plan?.ww??{};
const remaining=Math.max(0,Number(ww.remainingKWh??ww.remaining_kWh??0));
const deadlineRaw=ww.deadlineTs??ww.deadline_ts??null;
const deadline=deadlineRaw?Date.parse(deadlineRaw):NaN;
const contract=String(plan?.contractType??plan?.contract_type??'FIXED').toUpperCase();
const slots=Array.isArray(plan?.slots)?plan.slots:[];
const eligible=slots.filter(s=>{const t=Date.parse(s.ts);return Number.isFinite(t)&&(!Number.isFinite(deadline)||t<deadline)&&!s.hardConflict;});
const slotKWh=.475, needed=Math.max(0,Math.ceil(remaining/slotKWh-1e-9));
const pvSlots=eligible.filter(s=>Number(s.pvSurplusW??s.pv_surplus_W??0)>=1900).sort((a,b)=>Number(b.pvSurplusW??b.pv_surplus_W??0)-Number(a.pvSurplusW??a.pv_surplus_W??0)||Date.parse(a.ts)-Date.parse(b.ts));
const selected=[],used=new Set();
for(const s of pvSlots){if(selected.length>=needed)break;selected.push(s);used.add(s.ts);}
if(selected.length<needed){const rest=eligible.filter(s=>!used.has(s.ts));rest.sort((a,b)=>{if(contract==='DYNAMIC'){const ap=Number.isFinite(Number(a.priceEurKWh??a.price_eur_kWh))?Number(a.priceEurKWh??a.price_eur_kWh):999,bp=Number.isFinite(Number(b.priceEurKWh??b.price_eur_kWh))?Number(b.priceEurKWh??b.price_eur_kWh):999;if(ap!==bp)return ap-bp;}return Date.parse(a.ts)-Date.parse(b.ts);});for(const s of rest){if(selected.length>=needed)break;selected.push(s);}}
selected.sort((a,b)=>Date.parse(a.ts)-Date.parse(b.ts));
const sourceRevision=plan.revision??plan.sourceRevision??null;
const out={schema:'EM2_WW_PLANNER_INTENT_V0.2',mode:'SHADOW',generatedAt:new Date().toISOString(),sourcePlannerRevision:sourceRevision,contractType:contract,remainingKWh:Number(remaining.toFixed(3)),deadlineTs:deadlineRaw,requiredSlots:needed,selectedSlots:selected.map(s=>({ts:s.ts,pvSurplusW:Number(s.pvSurplusW??s.pv_surplus_W??0),priceEurKWh:Number.isFinite(Number(s.priceEurKWh??s.price_eur_kWh))?Number(s.priceEurKWh??s.price_eur_kWh):null,reason:Number(s.pvSurplusW??s.pv_surplus_W??0)>=1900?'PV_FIRST':(contract==='DYNAMIC'?'CHEAPEST_REQUIRED':'REQUIRED_BEFORE_DEADLINE')})),deadlineFeasible:selected.length>=needed,readOnly:true,deviceReads:false,deviceWrites:false,physicalWritePerformed:false,physicalWriterOwner:'EXISTING_WW_CONTROL'};
const text=JSON.stringify(out),ov=byName(VAR_OUT); if(ov){if(ov.value!==text)await Homey.logic.updateVariable({id:ov.id,variable:{value:text}});}else await Homey.logic.createVariable({variable:{name:VAR_OUT,type:'string',value:text}});
return true;
