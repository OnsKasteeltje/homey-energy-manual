// EM v2 | 05 P1 Rolling Sampler | v0.1
// 60 s sampling, 120 s rolling window. P1 + = import, - = export.
// No physical writes. Only publishes EM2_P1_Rolling Logic state.
const P1_ID='7a696d77-15fb-4b68-9bce-f1e39bff5045';
const VAR_NAME='EM2_P1_Rolling';
const WINDOW_MS=120000,FRESH_MS=90000,MIN_SAMPLE_GAP_MS=30000;
const now=Date.now();

const [p1,vars]=await Promise.all([
  Homey.devices.getDevice({id:P1_ID}),
  Homey.logic.getVariables()
]);
const gridW=Number(p1?.capabilitiesObj?.measure_power?.value);
if(!Number.isFinite(gridW))return false;

let outVar=Object.values(vars).find(v=>v.name===VAR_NAME)||null;
let prev=null;
try{prev=outVar?JSON.parse(String(outVar.value||'')):null;}catch{}

let samples=(Array.isArray(prev?.samples)?prev.samples:[])
  .filter(s=>Number.isFinite(Number(s?.ts))&&Number.isFinite(Number(s?.gridW)))
  .map(s=>({ts:Number(s.ts),gridW:Number(s.gridW)}))
  .filter(s=>now-s.ts>=0&&now-s.ts<=WINDOW_MS);

const last=samples.at(-1);
if(!last||now-last.ts>=MIN_SAMPLE_GAP_MS)samples.push({ts:now,gridW:Math.round(gridW)});
samples=samples.filter(s=>now-s.ts>=0&&now-s.ts<=WINDOW_MS);
if(samples.length===0)return false;

const avgGridW=Math.round(samples.reduce((sum,s)=>sum+s.gridW,0)/samples.length);
const oldest=samples[0],newest=samples.at(-1);
const out={
  schema:'EM2_P1_ROLLING_V0.1',
  generatedAt:new Date(now).toISOString(),
  windowSec:120,
  avgGridW,
  sampleCount:samples.length,
  oldestAt:new Date(oldest.ts).toISOString(),
  newestAt:new Date(newest.ts).toISOString(),
  fresh:now-newest.ts<=FRESH_MS,
  samples
};
const value=JSON.stringify(out);
if(!outVar){
  outVar=await Homey.logic.createVariable({variable:{name:VAR_NAME,type:'string',value}});
}else if(outVar.value!==value){
  await Homey.logic.updateVariable({id:outVar.id,variable:{value}});
}
return true;
