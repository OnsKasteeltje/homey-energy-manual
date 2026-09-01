'use strict';

const fs = require('fs');
const path = require('path');

const BASELINE = path.resolve(__dirname, '../src/homey/core/core-v0.11f.live-homey.js');
const OUTPUT = path.resolve(__dirname, '../build/core-v0.11g-planner-v05.candidate.js');

function replaceExactlyOnce(source, before, after, label) {
  const first = source.indexOf(before);
  if (first < 0) throw new Error(`Missing expected baseline fragment: ${label}`);
  const second = source.indexOf(before, first + before.length);
  if (second >= 0) throw new Error(`Expected exactly one baseline fragment: ${label}`);
  return source.slice(0, first) + after + source.slice(first + before.length);
}

function buildCandidate(source) {
  let out = source;

  out = replaceExactlyOnce(
    out,
    '// EM v2 | 00 Core Tick | v0.11f — Planner WW + Tesla intent + projected-grid headroom',
    '// EM v2 | 00 Core Tick | v0.11g CANDIDATE — Planner v0.5 WW compatibility + existing Tesla headroom',
    'header version',
  );

  out = replaceExactlyOnce(
    out,
    "const PUB_VERSION='EM2_CORE_STATE_V0.11f'",
    "const PUB_VERSION='EM2_CORE_STATE_V0.11g'",
    'publication version',
  );

  const oldParser = "const plannerSnap=parse(vv('EM2_Energy_Planner_Snapshot')),plannerAtMs=Date.parse(String(plannerSnap?.generatedAt||plannerSnap?.plan?.generatedAt||'')),plannerFresh=Number.isFinite(plannerAtMs)&&Date.now()-plannerAtMs>=0&&Date.now()-plannerAtMs<=PLANNER_FRESH_MS,plannerCompatible=plannerFresh&&String(plannerSnap?.plan?.schema||'')==='EM2_ENERGY_PLAN_24H_V0.4.9',plannerActions=plannerCompatible&&Array.isArray(plannerSnap?.plan?.plan?.actions)?plannerSnap.plan.plan.actions:[],plannerSlot=plannerActions.find(a=>{const s=Date.parse(String(a?.start||'')),e=Date.parse(String(a?.end||''));return Number.isFinite(s)&&Number.isFinite(e)&&s<=Date.now()&&Date.now()<e;})||null,plannerWW=String(plannerSlot?.warmWater||'HOLD').toUpperCase(),plannerWWReason=String(plannerSlot?.warmWaterReason||'UNKNOWN'),plannerWWStart=plannerSlot?.start??null,plannerWWEnd=plannerSlot?.end??null,plannerTesla=String(plannerSlot?.tesla||'HOLD').toUpperCase(),plannerTeslaStart=plannerSlot?.start??null,plannerTeslaEnd=plannerSlot?.end??null;";

  const newParser = "const plannerSnap=parse(vv('EM2_Energy_Planner_Snapshot')),plannerAtMs=Date.parse(String(plannerSnap?.generatedAt||plannerSnap?.plan?.generatedAt||'')),plannerFresh=Number.isFinite(plannerAtMs)&&Date.now()-plannerAtMs>=0&&Date.now()-plannerAtMs<=PLANNER_FRESH_MS,plannerSchema=String(plannerSnap?.plan?.schema||''),plannerSchemaSupported=plannerSchema==='EM2_ENERGY_PLAN_24H_V0.4.9'||plannerSchema==='EM2_ENERGY_PLAN_24H_V0.5.0',plannerActions=plannerFresh&&plannerSchemaSupported&&Array.isArray(plannerSnap?.plan?.plan?.actions)?plannerSnap.plan.plan.actions:[],plannerSlotRaw=plannerActions.find(a=>{const s=Date.parse(String(a?.start||'')),e=Date.parse(String(a?.end||''));return Number.isFinite(s)&&Number.isFinite(e)&&s<=Date.now()&&Date.now()<e;})||null,plannerSlotLocalDate=String(plannerSlotRaw?.localDate||''),plannerDateParts=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Amsterdam',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now),plannerDatePart=t=>plannerDateParts.find(x=>x.type===t)?.value,plannerToday=`${plannerDatePart('year')}-${plannerDatePart('month')}-${plannerDatePart('day')}`,plannerSlotRelation=String(plannerSlotRaw?.warmWaterDayRelation||''),plannerRawWW=String(plannerSlotRaw?.warmWater||'HOLD').toUpperCase(),plannerRawWwTarget=plannerSlotRaw?.targets?.wwTargetW,plannerV05TargetValid=plannerRawWwTarget===0||plannerRawWwTarget===BUDGET.boilerExpectedW,plannerV05DayValid=plannerSlotLocalDate===plannerToday&&(plannerSlotRelation===''||plannerSlotRelation==='CURRENT_DAY'),plannerV05ActionValid=plannerRawWwTarget===0?plannerRawWW==='HOLD':(plannerRawWW==='PV_PREFERRED'||plannerRawWW==='DEADLINE_REQUIRED'),plannerSlotContractValid=plannerSchema==='EM2_ENERGY_PLAN_24H_V0.4.9'?!!plannerSlotRaw:plannerSchema==='EM2_ENERGY_PLAN_24H_V0.5.0'?!!plannerSlotRaw&&plannerV05TargetValid&&plannerV05DayValid&&plannerV05ActionValid:false,plannerCompatible=plannerFresh&&plannerSchemaSupported&&plannerSlotContractValid,plannerSlot=plannerCompatible?plannerSlotRaw:null,plannerWW=plannerCompatible?(plannerSchema==='EM2_ENERGY_PLAN_24H_V0.5.0'?(plannerRawWwTarget===BUDGET.boilerExpectedW?plannerRawWW:'HOLD'):plannerRawWW):'HOLD',plannerWWReason=plannerCompatible?String(plannerSlot?.warmWaterReason||'UNKNOWN'):'INCOMPATIBLE_OR_STALE',plannerWWStart=plannerCompatible?plannerSlot?.start??null:null,plannerWWEnd=plannerCompatible?plannerSlot?.end??null:null,plannerTesla=plannerCompatible?String(plannerSlot?.tesla||'HOLD').toUpperCase():'HOLD',plannerTeslaStart=plannerCompatible?plannerSlot?.start??null:null,plannerTeslaEnd=plannerCompatible?plannerSlot?.end??null:null;";

  out = replaceExactlyOnce(out, oldParser, newParser, 'planner parser');

  out = replaceExactlyOnce(
    out,
    "plannerPolicy:'PLANNER_V0.4.9_SLOT_INTENT_WITH_REALTIME_CORE_SAFETY'",
    "plannerPolicy:'PLANNER_V0.4.9_V0.5.0_SLOT_INTENT_WITH_REALTIME_CORE_SAFETY'",
    'planner policy label',
  );

  return out;
}

if (require.main === module) {
  const source = fs.readFileSync(BASELINE, 'utf8');
  const candidate = buildCandidate(source);
  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
  fs.writeFileSync(OUTPUT, candidate);
  console.log(`Wrote ${path.relative(process.cwd(), OUTPUT)}`);
}

module.exports = { buildCandidate, replaceExactlyOnce, BASELINE, OUTPUT };
