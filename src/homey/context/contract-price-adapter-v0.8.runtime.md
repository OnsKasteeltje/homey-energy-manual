# EM v2 | 30 Context | Contract Price Adapter v0.8

- Homey flow ID: `b1c495cb-6ccd-4fb8-b4bf-365845dbb6e7`
- Type: Advanced Flow
- Runtime state at capture: `enabled=false`, `broken=false`, `triggerable=true`
- Trigger: every 15 minutes + manual start
- Capture date: 2026-08-28
- Status: exact runtime baseline captured; not yet promoted/refactored

## Runtime structure

1. HomeyScript condition: normalizes `EMS_ContractType` and mirrors `EM2_Contract_Type`.
2. DYNAMIC path: PBTH `prices_json(next_hours)` → `TEMP_PBTH_JSON_BUFFER`.
3. HomeyScript action: builds uniform contract-price context and writes `EM2_ContractPrice_*` variables.

## Runtime HomeyScript — contract selector

```js
// Contract Price Adapter v0.8 — EMS_ContractType is authoritative.
const vs=await Homey.logic.getVariables();
const b=Object.fromEntries(Object.values(vs).map(v=>[v.name,v]));
const ensure=async(n,t,val)=>{if(!b[n]) b[n]=await Homey.logic.createVariable({variable:{name:n,type:t,value:val}});};
const set=async(n,t,val)=>{let v=b[n];if(v){if(v.value!==val){await Homey.logic.updateVariable({id:v.id,variable:{value:val}});v.value=val;}}else{v=await Homey.logic.createVariable({variable:{name:n,type:t,value:val}});b[n]=v;}};
await ensure('EMS_ContractType','string','FIXED');
await ensure('EM2_Contract_Type','string','FIXED');
await ensure('EM2_Contract_EndDate','string','2026-09-25');
await ensure('EM2_Fixed_Import_Normal','number',0.23790);
await ensure('EM2_Fixed_Import_Offpeak','number',0.23548);
await ensure('EM2_Fixed_Export','number',0.15000);
await ensure('EM2_Fixed_Offpeak_Active','boolean',false);
await ensure('EM2_Contract_Config_Schema','string','EM2_CONTRACT_CONFIG_V0.3');
let contract=String(b.EMS_ContractType?.value||'FIXED').toUpperCase();
if(!['FIXED','DYNAMIC'].includes(contract)){contract='FIXED';await set('EMS_ContractType','string',contract);}
await set('EM2_Contract_Type','string',contract);
return contract==='DYNAMIC';
```

## Runtime HomeyScript — uniform price context

```js
// Uniform contract price context v0.8 — FIXED path performs no device enumeration.
const PBTH='d28cdd44-ab8c-4f4c-8ea7-279f444ecd81',STEP=15*60000,ECON=0.02;
const vs=await Homey.logic.getVariables();
const b=Object.fromEntries(Object.values(vs).map(v=>[v.name,v]));
const set=async(n,t,val)=>{const v=b[n];if(v){if(v.value!==val){await Homey.logic.updateVariable({id:v.id,variable:{value:val}});v.value=val;}}else b[n]=await Homey.logic.createVariable({variable:{name:n,type:t,value:val}});};
const bool=v=>v===true||String(v).toLowerCase()==='true',num=v=>Number.isFinite(Number(v))?Number(v):null,avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:null,pct=(a,p)=>{if(!a.length)return null;const s=[...a].sort((x,y)=>x-y),i=(s.length-1)*p,lo=Math.floor(i),hi=Math.ceil(i);return lo===hi?s[lo]:s[lo]+(s[hi]-s[lo])*(i-lo);};
let contract=String(b.EMS_ContractType?.value||'FIXED').toUpperCase();if(!['FIXED','DYNAMIC'].includes(contract))contract='FIXED';
let imp=null,exp=null,neg=false,cheap=false,expensive=false,cheapNow=false,expensiveNow=false,quality='GOOD',source='',horizonHours=0,horizon='',min4=null,max4=null,avg4=null,p25=null,p75=null;
if(contract==='FIXED'){
 const off=bool(b.EM2_Fixed_Offpeak_Active?.value),normal=num(b.EM2_Fixed_Import_Normal?.value),low=num(b.EM2_Fixed_Import_Offpeak?.value),ex=num(b.EM2_Fixed_Export?.value);
 imp=off?low:normal;exp=ex;quality=[normal,low,ex].every(v=>v!==null&&v>=0)?'GOOD':'DEGRADED';source='FIXED_CONFIG';horizon='STATIC';horizonHours=168;neg=false;
 cheapNow=quality==='GOOD'&&off&&(normal-low)>=ECON;expensiveNow=quality==='GOOD'&&!off&&(normal-low)>=ECON;cheap=cheapNow;expensive=expensiveNow;
 min4=Math.min(normal??Infinity,low??Infinity);max4=Math.max(normal??-Infinity,low??-Infinity);avg4=imp;p25=min4;p75=max4;
}else{
 const ds=await Homey.devices.getDevices();
 const d=ds[PBTH],cap=k=>d?.capabilitiesObj?.[k]?.value;imp=num(cap('meter_price_h0'));exp=num(cap('meter_price_h0_export'));
 const raw=String(b.TEMP_PBTH_JSON_BUFFER?.value??'');let arr=null;try{arr=JSON.parse(raw);}catch{}const prices=Array.isArray(arr)?arr.map(Number):[];let valid=0;for(const p of prices){if(!Number.isFinite(p)||p<=-2||p>=5)break;valid++;}
 const vprices=prices.slice(0,valid),next4=vprices.slice(0,Math.min(16,vprices.length));horizonHours=Math.max(0,valid*STEP/3600000);quality=d&&imp!==null&&valid>=4?'GOOD':'DEGRADED';source='PBTH_DAP15_DIRECT_CLASSIFIER';horizon=horizonHours>=12?'FULL':horizonHours>=6?'INTRADAY':'DIAGNOSTIC';
 p25=pct(vprices,0.25);p75=pct(vprices,0.75);min4=next4.length?Math.min(...next4):null;max4=next4.length?Math.max(...next4):null;avg4=avg(next4);neg=quality==='GOOD'&&imp<0;
 cheapNow=quality==='GOOD'&&p25!==null&&imp<=p25&&(avg4===null||avg4-imp>=ECON);expensiveNow=quality==='GOOD'&&p75!==null&&imp>=p75&&(avg4===null||imp-avg4>=ECON);cheap=quality==='GOOD'&&avg4!==null&&p25!==null&&avg4<=p25;expensive=quality==='GOOD'&&avg4!==null&&p75!==null&&avg4>=p75;
}
const selfUse=imp!==null&&exp!==null?imp-exp:null,now=new Date().toISOString();
const ctx={schema:'EM2_UNIFORM_PRICE_CONTEXT_V0.3',contractType:contract,contractEndDate:String(b.EM2_Contract_EndDate?.value||''),source,quality,updatedAt:now,importPriceNow:imp,exportPriceNow:exp,selfUseGainNow:selfUse,negativeNow:neg,cheapNow,expensiveNow,cheapNext4h:cheap,expensiveNext4h:expensive,statistics:{minNext4h:min4,maxNext4h:max4,avgNext4h:avg4,p25AvailableHorizon:p25,p75AvailableHorizon:p75,economicThreshold:ECON},horizon,horizonHours,guards:{canonicalContractSource:'EMS_ContractType',contractIndependentOutput:true,fixedDoesNotDependOnPBTH:contract==='FIXED',dynamicPriceFlagsDirectFromPBTH:contract==='DYNAMIC',legacyM7PriceInputs:false,shadowNamespaceIsolated:true,noActuatorWrites:true}};
await set('EM2_Contract_Type','string',contract);await set('EM2_ContractPrice_Context','string',JSON.stringify(ctx));await set('EM2_ContractPrice_Import_Now','number',imp??-99);await set('EM2_ContractPrice_Export_Now','number',exp??-99);await set('EM2_ContractPrice_SelfUse_Gain','number',selfUse??-99);await set('EM2_ContractPrice_Negative','boolean',neg);await set('EM2_ContractPrice_Cheap_Now','boolean',cheapNow);await set('EM2_ContractPrice_Expensive_Now','boolean',expensiveNow);await set('EM2_ContractPrice_Cheap_Next4h','boolean',cheap);await set('EM2_ContractPrice_Expensive_Next4h','boolean',expensive);await set('EM2_ContractPrice_Min_Next4h','number',min4??-99);await set('EM2_ContractPrice_Max_Next4h','number',max4??-99);await set('EM2_ContractPrice_Avg_Next4h','number',avg4??-99);await set('EM2_ContractPrice_P25','number',p25??-99);await set('EM2_ContractPrice_P75','number',p75??-99);await set('EM2_ContractPrice_Source','string',source);await set('EM2_ContractPrice_Quality','string',quality);await set('EM2_ContractPrice_Horizon','string',horizon);await set('EM2_ContractPrice_HorizonHours','number',horizonHours);await set('EM2_ContractPrice_UpdatedAt','string',now);return true;
```

## Runtime note

`v0.8 — EMS_ContractType is the only authoritative contract setting. EM2_Contract_Type is compatibility mirror. FIXED does not depend on PBTH/M7; DYNAMIC classifies directly from PBTH.`
