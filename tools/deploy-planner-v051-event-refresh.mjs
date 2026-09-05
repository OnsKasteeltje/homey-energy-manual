#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';

const require = createRequire('/home/jeroen/ems-homey-adapter/package.json');
const { HomeyAPI } = require('homey-api');

const HOMEY='http://192.168.1.58';
const TOKEN_FILE=`${process.env.HOME}/.config/ems-pi/homey-api-key`;
const REPO='/home/jeroen/ems/repo/homey-energy-manual';
const CORE_ID='227f8d3b-7551-46dd-837d-1b8c69add824';
const PLANNER_ID='27617767-0a64-43a3-9bcb-e34b0dd6a5c0';
const HOTFIX_ID='4b3eda5a-4ab9-4fd2-8358-5d71b9c5a82d';
const PLANNER_INPUT_ID='39c7c169-34d7-4e14-a27b-520aca255032';
const PLANNER_SNAPSHOT_ID='b9f1232c-ac01-45fa-9453-ef95d998b138';
const MARKER_NAME='EM2_EV_Goal_Input_Status';
const RUN='homey:app:com.athom.homeyscript:runCode_v2';
const VAR_CHANGED='homey:manager:logic:variable_changed';

const token=fs.readFileSync(TOKEN_FILE,'utf8').trim();
const homey=await HomeyAPI.createLocalAPI({address:HOMEY,token});
const stamp=new Date().toISOString().replace(/[:.]/g,'-');
const backupDir=path.join(REPO,'tmp',`planner-v051-backup-${stamp}`);
fs.mkdirSync(backupDir,{recursive:true});

const clone=o=>JSON.parse(JSON.stringify(o));
const writable=f=>({name:f.name,enabled:f.enabled,folder:f.folder??null,cards:f.cards});
const one=(cards,pred,label)=>{const x=Object.entries(cards).filter(([,c])=>pred(c));if(x.length!==1)throw new Error(`${label}: expected 1 card, got ${x.length}`);return x[0];};
const replaceOne=(s,oldText,newText,label)=>{const n=s.split(oldText).length-1;if(n!==1)throw new Error(`${label}: expected 1 exact match, got ${n}`);return s.replace(oldText,newText);};
const uuid=()=>crypto.randomUUID();

const vars=await homey.logic.getVariables();
const marker=Object.values(vars).find(v=>v.name===MARKER_NAME);
if(!marker)throw new Error(`${MARKER_NAME} not found`);

const core0=await homey.flow.getAdvancedFlow({id:CORE_ID});
const planner0=await homey.flow.getAdvancedFlow({id:PLANNER_ID});
const hotfix0=await homey.flow.getAdvancedFlow({id:HOTFIX_ID});
if(core0.enabled!==false)throw new Error('ABORT: Core must be OFF before deployment');
if(core0.broken||planner0.broken||hotfix0.broken)throw new Error('ABORT: one baseline flow is already broken');
for(const [name,obj] of [['core',core0],['planner',planner0],['hotfix',hotfix0]])fs.writeFileSync(path.join(backupDir,`${name}.json`),JSON.stringify(obj,null,2));

const core=clone(core0), planner=clone(planner0);
const [coreScriptId,coreScript]=one(core.cards,c=>c.type==='action'&&c.id===RUN,'Core HomeyScript');
const [plannerScriptId,plannerScript]=one(planner.cards,c=>c.type==='action'&&c.id===RUN,'Planner HomeyScript');

// Core v0.11i: expose already-read max current to Planner. No extra Homey read, no physical write.
if(!coreScript.args.code.includes("teslaMaxA:vv('EV Max laadstroom A')")){
  coreScript.args.code=replaceOne(
    coreScript.args.code,
    "goals:{teslaDeadlineActive:vv('EV Deadline actief'),teslaDeadline:vv('EV Deadline tijd'),teslaLatestStart:vv('EV Latest start'),teslaRemainingKWh:vv('EV Resterend kWh'),teslaStatus:vv('EV Deadline status')}",
    "goals:{teslaDeadlineActive:vv('EV Deadline actief'),teslaDeadline:vv('EV Deadline tijd'),teslaLatestStart:vv('EV Latest start'),teslaRemainingKWh:vv('EV Resterend kWh'),teslaStatus:vv('EV Deadline status'),teslaMaxA:vv('EV Max laadstroom A')}",
    'Core teslaMaxA patch'
  );
}

// Event-driven Core refresh: semantic deadline adapter marker changes only.
const coreHasMarker=Object.values(core.cards).some(c=>c.type==='trigger'&&c.id===VAR_CHANGED&&c.args?.variable?.id===marker.id);
if(!coreHasMarker){
  const id=uuid();
  core.cards[id]={type:'trigger',id:VAR_CHANGED,x:-320,y:330,args:{variable:{id:marker.id,name:MARKER_NAME}},outputSuccess:[coreScriptId]};
}

// Canonical Planner v0.5.1 allocation patch.
let p=plannerScript.args.code;
if(!p.includes("EM2_ENERGY_PLAN_24H_V0.5.1")){
  p=replaceOne(p,"const VERSION='EM2_ENERGY_PLAN_24H_V0.5.0',STEP_MS=15*60000,MAX_SLOTS=96;","const VERSION='EM2_ENERGY_PLAN_24H_V0.5.1',STEP_MS=15*60000,MAX_SLOTS=96;",'Planner version');
  p=replaceOne(p,"const EV_OPPORTUNITY_START_MIN_W=4830,EV_OPPORTUNITY_CONTINUE_MIN_W=4140,EV_OPPORTUNITY_MIN_RUN_SLOTS=2;","const EV_OPPORTUNITY_START_MIN_W=4830,EV_OPPORTUNITY_CONTINUE_MIN_W=4140,EV_OPPORTUNITY_MIN_RUN_SLOTS=2;\nconst EV_W_PER_A=690,EV_MIN_A=6,EV_MAX_A=16;",'Planner EV constants');
  p=replaceOne(p,
    "const deadlineActive=bool(state?.goals?.teslaDeadlineActive),remainingKWh=Math.max(0,num(state?.goals?.teslaRemainingKWh)||0),deadlineAt=state?.goals?.teslaDeadline??null,latestStart=state?.goals?.teslaLatestStart??null;",
    "const deadlineActive=bool(state?.goals?.teslaDeadlineActive),remainingKWh=Math.max(0,num(state?.goals?.teslaRemainingKWh)||0),deadlineAt=state?.goals?.teslaDeadline??null,latestStart=state?.goals?.teslaLatestStart??null,maxA=Math.max(EV_MIN_A,Math.min(EV_MAX_A,Math.round(num(state?.goals?.teslaMaxA)||EV_MAX_A))),maxPowerW=maxA*EV_W_PER_A,evSlotEnergyKWh=maxPowerW/1000*.25,requiredDeadlineSlots=deadlineActive&&remainingKWh>0?Math.ceil(remainingKWh/evSlotEnergyKWh-1e-12):0,latestStartMs=Date.parse(String(latestStart||'')),deadlineCatchUp=deadlineActive&&Number.isFinite(latestStartMs)&&nowMs>=latestStartMs;",
    'Planner deadline derivation'
  );
  p=replaceOne(p,
    "const teslaCandidates=forecastSlots.filter(s=>before(s,dlMs));\nconst teslaDeadlineRanked=deadlineActive&&remainingKWh>0?rankTeslaDeadline(teslaCandidates).slice(0,Math.min(12,teslaCandidates.length)):[];",
    "const teslaCandidates=forecastSlots.filter(s=>before(s,dlMs));\nconst teslaDeadlineOrdered=deadlineCatchUp?[...teslaCandidates].sort((a,z)=>Date.parse(a.start)-Date.parse(z.start)):rankTeslaDeadline(teslaCandidates);\nconst teslaDeadlineRanked=deadlineActive&&remainingKWh>0?teslaDeadlineOrdered.slice(0,Math.min(requiredDeadlineSlots,teslaDeadlineOrdered.length)):[];\nconst teslaAllocatedKWh=teslaDeadlineRanked.length*evSlotEnergyKWh,teslaUnallocatedKWh=Math.max(0,remainingKWh-teslaAllocatedKWh);",
    'Planner deadline slots'
  );
  p=replaceOne(p,
    "for(const x of teslaDeadlineRanked)if(byStart[x.start])byStart[x.start].tesla='PREFERRED_BEFORE_DEADLINE';",
    "for(const x of teslaDeadlineRanked)if(byStart[x.start]){byStart[x.start].tesla=deadlineCatchUp?'DEADLINE_REQUIRED':'PREFERRED_BEFORE_DEADLINE';byStart[x.start].targets.evTargetW=maxPowerW;}",
    'Planner EV target write'
  );
  p=replaceOne(p,
    "tesla:{deadlineActive,remainingKWh,deadlineAt,latestStart,throughputModel:'NOT_ASSUMED'",
    "tesla:{deadlineActive,remainingKWh,deadlineAt,latestStart,maxA,maxPowerW,slotEnergyKWh:Number(evSlotEnergyKWh.toFixed(3)),requiredDeadlineSlots,deadlineCatchUp,throughputModel:'NOT_ASSUMED'",
    'Planner input Tesla evidence'
  );
  p=replaceOne(p,
    "obligationKWh:deadlineActive?remainingKWh:0,deadlineAt,allocationPolicy:teslaAllocationPolicy}",
    "obligationKWh:deadlineActive?remainingKWh:0,deadlineAt,allocatedKWh:Number(teslaAllocatedKWh.toFixed(3)),unallocatedKWh:Number(teslaUnallocatedKWh.toFixed(3)),maxA,maxPowerW,requiredDeadlineSlots,deadlineCatchUp,allocationPolicy:teslaAllocationPolicy}",
    'Planner plan Tesla evidence'
  );
  p=replaceOne(p,
    "teslaAllocationPolicy,wwObligation",
    "teslaAllocationPolicy,teslaMaxA:maxA,teslaMaxPowerW:maxPowerW,teslaRequiredSlots:requiredDeadlineSlots,teslaAllocatedSlots:teslaDeadlineRanked.length,teslaUnallocatedKWh:Number(teslaUnallocatedKWh.toFixed(3)),teslaDeadlineCatchUp:deadlineCatchUp,wwObligation",
    'Planner status evidence'
  );
  p=p.replaceAll('READY_SHADOW_V0.5.0','READY_SHADOW_V0.5.1');
  p=p.replaceAll('Homey-EMS-Planner-v0.5.0','Homey-EMS-Planner-v0.5.1');
}
plannerScript.args.code=p;
planner.name='EM v2 | 45 Planner | 24h Energy Plan v0.5.1 SHADOW LOW-LOAD';

// Low-load event refresh: same semantic deadline marker, but delayed so Core can publish fresh Planner Input first.
const plannerHasMarker=Object.values(planner.cards).some(c=>c.type==='trigger'&&c.id===VAR_CHANGED&&c.args?.variable?.id===marker.id);
if(!plannerHasMarker){
  const trig=uuid(),delay=uuid();
  planner.cards[trig]={type:'trigger',id:VAR_CHANGED,x:-320,y:330,args:{variable:{id:marker.id,name:MARKER_NAME}},outputSuccess:[delay]};
  planner.cards[delay]={type:'delay',x:0,y:330,args:{delay:{number:'8',multiplier:1}},outputSuccess:[plannerScriptId]};
}

// Save exact patched runtime sources locally before changing Homey.
fs.writeFileSync(path.join(backupDir,'core-v0.11i.patched.js'),coreScript.args.code);
fs.writeFileSync(path.join(backupDir,'planner-v0.5.1.patched.js'),plannerScript.args.code);

let plannerDisabled=false;
try{
  // Planner briefly OFF only while its graph is replaced; Core stays OFF throughout.
  await homey.flow.updateAdvancedFlow({id:PLANNER_ID,advancedflow:writable({...planner0,enabled:false})});
  plannerDisabled=true;
  planner.enabled=true;
  await homey.flow.updateAdvancedFlow({id:PLANNER_ID,advancedflow:writable(planner)});
  await homey.flow.updateAdvancedFlow({id:CORE_ID,advancedflow:writable(core)});

  const c1=await homey.flow.getAdvancedFlow({id:CORE_ID});
  const p1=await homey.flow.getAdvancedFlow({id:PLANNER_ID});
  if(c1.enabled!==false||c1.broken)throw new Error(`Core verify failed enabled=${c1.enabled} broken=${c1.broken}`);
  if(p1.enabled!==true||p1.broken)throw new Error(`Planner verify failed enabled=${p1.enabled} broken=${p1.broken}`);
  const cCode=one(c1.cards,c=>c.type==='action'&&c.id===RUN,'Core verify script')[1].args.code;
  const pCode=one(p1.cards,c=>c.type==='action'&&c.id===RUN,'Planner verify script')[1].args.code;
  if(!cCode.includes("teslaMaxA:vv('EV Max laadstroom A')"))throw new Error('Core verify: teslaMaxA absent');
  if(!pCode.includes("EM2_ENERGY_PLAN_24H_V0.5.1"))throw new Error('Planner verify: v0.5.1 absent');
  if(!Object.values(c1.cards).some(c=>c.type==='trigger'&&c.id===VAR_CHANGED&&c.args?.variable?.id===marker.id))throw new Error('Core verify: deadline event trigger absent');
  if(!Object.values(p1.cards).some(c=>c.type==='trigger'&&c.id===VAR_CHANGED&&c.args?.variable?.id===marker.id))throw new Error('Planner verify: deadline event trigger absent');

  // Shadow-only smoke: manual Planner run using current Planner Input. Core remains OFF.
  const oldSnap=JSON.parse(String((await homey.logic.getVariable({id:PLANNER_SNAPSHOT_ID})).value||'null'));
  await homey.flow.triggerAdvancedFlow({id:PLANNER_ID});
  let snap=null;
  for(let i=0;i<20;i++){
    await new Promise(r=>setTimeout(r,1000));
    try{snap=JSON.parse(String((await homey.logic.getVariable({id:PLANNER_SNAPSHOT_ID})).value||'null'));}catch{}
    if(snap?.plan?.schema==='EM2_ENERGY_PLAN_24H_V0.5.1'&&snap?.generatedAt!==oldSnap?.generatedAt)break;
  }
  if(snap?.plan?.schema!=='EM2_ENERGY_PLAN_24H_V0.5.1')throw new Error('Smoke verify: fresh v0.5.1 snapshot not observed');
  const ti=snap?.plan?.inputs?.tesla||{},tp=snap?.plan?.plan?.tesla||{};
  if(!Object.hasOwn(ti,'maxA')||!Object.hasOwn(ti,'requiredDeadlineSlots')||!Object.hasOwn(tp,'allocatedKWh'))throw new Error('Smoke verify: v0.5.1 Tesla evidence incomplete');

  // Canonical Planner is proven; retire TEMP hotfix, but do not delete it.
  const hf=await homey.flow.getAdvancedFlow({id:HOTFIX_ID});
  if(hf.enabled){hf.enabled=false;hf.name='TEMP | Planner EV Deadline Allocation v0.5.1 HOTFIX [DISABLED]';await homey.flow.updateAdvancedFlow({id:HOTFIX_ID,advancedflow:writable(hf)});}
  const hf1=await homey.flow.getAdvancedFlow({id:HOTFIX_ID});
  if(hf1.enabled||hf1.broken)throw new Error('TEMP hotfix disable verify failed');

  // Keep local canonical files aligned with the exact deployed HomeyScript source.
  fs.writeFileSync(path.join(REPO,'src/homey/core/core-v0.11i.live-homey.js'),cCode+'\n');
  fs.writeFileSync(path.join(REPO,'src/homey/planner/energy-plan-24h-v0.5.1.live-homey.js'),pCode+'\n');

  console.log(JSON.stringify({
    result:'PASS',
    core:{enabled:c1.enabled,broken:c1.broken,eventRefresh:true,teslaMaxA:true},
    planner:{enabled:p1.enabled,broken:p1.broken,version:snap.plan.schema,eventRefresh:true,sourceRevision:snap.sourceRevision,deadlineActive:ti.deadlineActive,maxA:ti.maxA,requiredDeadlineSlots:ti.requiredDeadlineSlots,allocatedKWh:tp.allocatedKWh,unallocatedKWh:tp.unallocatedKWh},
    tempHotfix:{enabled:hf1.enabled,broken:hf1.broken},
    backupDir,
    note:'Core intentionally remains OFF. Do not enable until reviewed.'
  },null,2));
}catch(e){
  console.error('DEPLOY FAILED — rolling back:',e?.stack||e);
  try{await homey.flow.updateAdvancedFlow({id:CORE_ID,advancedflow:writable(core0)});}catch(x){console.error('Core rollback failed',x);}
  try{await homey.flow.updateAdvancedFlow({id:PLANNER_ID,advancedflow:writable(planner0)});}catch(x){console.error('Planner rollback failed',x);}
  try{await homey.flow.updateAdvancedFlow({id:HOTFIX_ID,advancedflow:writable(hotfix0)});}catch(x){console.error('Hotfix rollback failed',x);}
  process.exitCode=1;
}
