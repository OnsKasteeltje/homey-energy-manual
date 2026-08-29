// Runtime capture 2026-08-30
// Flow ID: 14027232-905e-4b8b-828d-5b44b8f6692e
// Homey runtime enabled=false, broken=false; every 5 min + manual start.
const VERSION='EM2_DAY_SERIES_LOCAL_V0.6.1';
const STATE_ID='8e1efbb0-7999-494c-9429-7d274afacd79';
const BUF_ID='254f15cd-b060-4b42-801d-5e4f58efa069';
const parse=v=>{try{return JSON.parse(String(v??'null'));}catch{return null;}};
const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
const localDay=d=>new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Amsterdam',year:'numeric',month:'2-digit',day:'2-digit'}).format(d);
const [stateV,bufV]=await Promise.all([Homey.logic.getVariable({id:STATE_ID}),Homey.logic.getVariable({id:BUF_ID})]);
const s=parse(stateV?.value),schema=String(s?.schema||''),sourceTs=Date.parse(String(s?.sampledAt||''));
if(!s||!/^ENERGY_STATE_V2\.\d+$/.test(schema)||!finite(s.revision)||!Number.isFinite(sourceTs))throw new Error(`EM2_State incompatibel: ${schema||'geen schema'}`);
const now=new Date(),day=localDay(now),sourceAgeSec=Math.max(0,Math.round((Date.now()-sourceTs)/1000));
const sample={ts:now.toISOString(),source_sample_at:s.sampledAt,revision:Number(s.revision),held:sourceAgeSec>120,p1W:finite(s?.grid?.powerW)?Number(s.grid.powerW):null,p1L1W:finite(s?.grid?.l1W)?Number(s.grid.l1W):null,p1L2W:finite(s?.grid?.l2W)?Number(s.grid.l2W):null,p1L3W:finite(s?.grid?.l3W)?Number(s.grid.l3W):null,p1Valid:s?.sourceTiming?.p1Fresh===true,solarEdgeW:Math.max(0,Number(s?.pv?.solarEdgeW)||0),goodWe4200W:Math.max(0,Number(s?.pv?.goodWe4200W)||0),goodWe2000W:Math.max(0,Number(s?.pv?.goodWe2000W)||0),teslaW:Math.max(0,Number(s?.tesla?.powerW)||0),boilerW:Math.max(0,Number(s?.hotWater?.boilerPowerW)||0),boilerOn:s?.hotWater?.boilerOn===true,washerActive:s?.appliances?.washerActive===true,dryerActive:s?.appliances?.dryerActive===true,source:'EM2_STATE'};
let hist=parse(bufV?.value);
if(!hist||hist.date_local!==day)hist={schema_version:'2.6',source:VERSION,date_local:day,sample_interval_minutes:5,measurement_control_independent:true,source_contract:'EM2_State',targeted_logic_reads_per_run:2,device_reads_per_run:0,network_calls_per_run:0,samples:[]};
hist.samples=(hist.samples||[]).filter(x=>{try{return localDay(new Date(x.ts))===day;}catch{return false;}});
const last=hist.samples.at(-1);if(!last||Date.parse(sample.ts)-Date.parse(last.ts)>=240000)hist.samples.push(sample);
hist.samples=hist.samples.slice(-300);hist.generated_at=now.toISOString();hist.sample_count=hist.samples.length;hist.health={status:sourceAgeSec>900?'STALE_CORE':sample.p1Valid?'OK':'P1_STALE',source_schema:schema,source_sample_at:s.sampledAt,source_age_sec:sourceAgeSec,held_sample:sample.held,producer:'EM v2 | 70 History | Day Series v0.6.1 TARGETED LOCAL SAMPLER',targeted_logic_reads_per_run:2,collection_reads_per_run:0,device_reads_per_run:0,network_calls_per_run:0,external_publication:false};
await Homey.logic.updateVariable({id:BUF_ID,variable:{value:JSON.stringify(hist)}});
return true;
