#!/usr/bin/env node
// One-shot EV phase SHADOW observer.
// Reads canonical Pi state + Pi control envelope, performs NO control/device writes,
// and writes only /home/jeroen/ems/data/ev-phase-shadow-state.json.
//
// Deliberately simple: when the production EV is physically idle, actualEvCommandA=0
// is known. While EV charging is active, this observer refuses to guess the actual
// production command; that can be added later if SHADOW validation proves useful.

import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {decideEvPhaseShadow} from '../../../../src/homey/ev/ev-phase-selector-shadow-v0.1.mjs';

const STATE_PATH='/home/jeroen/ems/data/energy-state-v2.json';
const OUT_PATH='/home/jeroen/ems/data/ev-phase-shadow-state.json';
const CONTROL_URL='http://127.0.0.1:3100/control/current';
const MAX_P1_AGE_MS=180000;

const readJson=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const n=v=>Number.isFinite(Number(v))?Number(v):null;

function fetchJson(url){
  return new Promise((resolve,reject)=>{
    const req=http.get(url,{timeout:3000},res=>{
      let body='';
      res.setEncoding('utf8');
      res.on('data',c=>body+=c);
      res.on('end',()=>{
        if(res.statusCode<200||res.statusCode>=300) return reject(new Error(`HTTP_${res.statusCode}`));
        try{ resolve(JSON.parse(body)); }catch(e){ reject(new Error('INVALID_CONTROL_JSON')); }
      });
    });
    req.on('timeout',()=>req.destroy(new Error('CONTROL_TIMEOUT')));
    req.on('error',reject);
  });
}

function atomicWriteJson(file,obj){
  const tmp=`${file}.tmp-${process.pid}`;
  fs.writeFileSync(tmp,JSON.stringify(obj,null,2)+'\n');
  fs.renameSync(tmp,file);
}

const now=Date.now();
const state=readJson(STATE_PATH);
const control=await fetchJson(CONTROL_URL);
let previous={};
try{ previous=readJson(OUT_PATH)?.decision||{}; }catch{}

const meta=state?.meta||{};
const grid=state?.grid||{};
const gate=state?.balance?.control_gate||{};
const tesla=state?.tesla||{};
const env=control?.realtime?.ev||{};

const sampleMs=Date.parse(String(meta.source_sample_at||''));
const p1AgeMs=Number.isFinite(sampleMs)?now-sampleMs:Infinity;
const p1Valid=
  gate.p1_fresh===true &&
  gate.grid_measurement_valid===true &&
  p1AgeMs>=0 &&
  p1AgeMs<=MAX_P1_AGE_MS &&
  [grid.power_w,grid.l1_w,grid.l2_w,grid.l3_w].every(v=>n(v)!==null);

const envelopeAllowed=
  control?.schema==='EMS_PI_CONTROL_COMMAND_V0.1' &&
  control?.status==='READY' &&
  control?.plannerOwner==='PI' &&
  env?.schema==='EMS_PI_EV_REALTIME_ENVELOPE_V0.3' &&
  env?.productionConsumerAllowed===true &&
  env?.allowed===true;

const charging=tesla?.charging===true;
const powerW=n(tesla?.power_w);
const physicallyIdle=charging===false && (powerW===null || Math.abs(powerW)<100);

let decision=null;
let observerStatus='READY';
let observerReason='PHYSICAL_EV_IDLE_COMMAND_IS_ZERO';

if(!p1Valid){
  observerStatus='INVALID_INPUT';
  observerReason='P1_NOT_FRESH_OR_VALID';
}else if(!envelopeAllowed){
  observerStatus='BLOCKED';
  observerReason='PI_REALTIME_ENVELOPE_NOT_ALLOWED';
}else if(!physicallyIdle){
  observerStatus='NEEDS_ACTUAL_COMMAND';
  observerReason='ACTIVE_EV_COMMAND_NOT_AVAILABLE_WITHOUT_GUESSING';
}else{
  decision=decideEvPhaseShadow({
    opportunityAllowed:true,
    maxA:n(env.max_A)??16,
    p1TotalW:n(grid.power_w),
    p1L1W:n(grid.l1_w),
    p1L2W:n(grid.l2_w),
    p1L3W:n(grid.l3_w),
    actualEvCommandA:0,
    actualEvPhaseCount:0
  },previous,now);
}

const out={
  schema:'EMS_PI_EV_PHASE_SHADOW_OBSERVER_V0.1',
  generatedAt:new Date(now).toISOString(),
  shadow:true,
  readOnly:true,
  deviceWrites:false,
  controlWrites:false,
  status:observerStatus,
  reason:observerReason,
  sources:{
    state:STATE_PATH,
    control:CONTROL_URL,
    p1SampleAt:meta.source_sample_at??null,
    p1AgeSec:Number.isFinite(p1AgeMs)?Math.round(p1AgeMs/1000):null,
    p1Fresh:gate.p1_fresh===true,
    gridMeasurementValid:gate.grid_measurement_valid===true,
    realtimeEnvelopeAllowed:envelopeAllowed,
    productionEvPhysicallyIdle:physicallyIdle
  },
  decision
};

atomicWriteJson(OUT_PATH,out);
console.log(JSON.stringify(out,null,2));
