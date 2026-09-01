'use strict';

const fs = require('fs');
const assert = require('assert');
const { buildCandidate, BASELINE } = require('../scripts/build-core-v0.11g-planner-v05-candidate');

const baseline = fs.readFileSync(BASELINE, 'utf8');
const candidate = buildCandidate(baseline);

assert(candidate.includes("PUB_VERSION='EM2_CORE_STATE_V0.11g'"));
assert(candidate.includes("plannerSchema==='EM2_ENERGY_PLAN_24H_V0.4.9'||plannerSchema==='EM2_ENERGY_PLAN_24H_V0.5.0'"));
assert(candidate.includes("plannerRawWwTarget===0||plannerRawWwTarget===BUDGET.boilerExpectedW"));
assert(candidate.includes("plannerSlotLocalDate===plannerToday"));
assert(candidate.includes("plannerRawWW==='PV_PREFERRED'||plannerRawWW==='DEADLINE_REQUIRED'"));
assert(candidate.includes("plannerPolicy:'PLANNER_V0.4.9_V0.5.0_SLOT_INTENT_WITH_REALTIME_CORE_SAFETY'"));
assert(!candidate.includes("plannerCompatible=plannerFresh&&String(plannerSnap?.plan?.schema||'')==='EM2_ENERGY_PLAN_24H_V0.4.9'"));

// Load discipline: integration must not add more Homey collection/device reads than the exact baseline.
const count = (s, re) => (s.match(re) || []).length;
assert.equal(count(candidate, /Homey\.logic\.getVariables\(\)/g), count(baseline, /Homey\.logic\.getVariables\(\)/g));
assert.equal(count(candidate, /Homey\.devices\.getDevice\(/g), count(baseline, /Homey\.devices\.getDevice\(/g));
assert.equal(count(candidate, /Homey\.logic\.getVariable\(/g), count(baseline, /Homey\.logic\.getVariable\(/g));
assert.equal(count(candidate, /Homey\.logic\.updateVariable\(/g), count(baseline, /Homey\.logic\.updateVariable\(/g));
assert.equal(count(candidate, /Homey\.logic\.createVariable\(/g), count(baseline, /Homey\.logic\.createVariable\(/g));

// Safety/writer discipline remains unchanged.
assert.equal(count(candidate, /setCapabilityValue/g), count(baseline, /setCapabilityValue/g));
assert.equal(count(candidate, /Homey\.flow\.triggerFlow/g), count(baseline, /Homey\.flow\.triggerFlow/g));
assert(candidate.includes('NO physical writes here.'));

// Scope discipline: only four deliberate substitutions are allowed.
let normalized = candidate
  .replace('// EM v2 | 00 Core Tick | v0.11g CANDIDATE — Planner v0.5 WW compatibility + existing Tesla headroom', '// EM v2 | 00 Core Tick | v0.11f — Planner WW + Tesla intent + projected-grid headroom')
  .replace("const PUB_VERSION='EM2_CORE_STATE_V0.11g'", "const PUB_VERSION='EM2_CORE_STATE_V0.11f'")
  .replace("plannerPolicy:'PLANNER_V0.4.9_V0.5.0_SLOT_INTENT_WITH_REALTIME_CORE_SAFETY'", "plannerPolicy:'PLANNER_V0.4.9_SLOT_INTENT_WITH_REALTIME_CORE_SAFETY'");

const newParserStart = "const plannerSnap=parse(vv('EM2_Energy_Planner_Snapshot')),plannerAtMs=";
const newParserEnd = ";\nconst sourceRevision=";
const baseStart = baseline.indexOf(newParserStart);
const baseEnd = baseline.indexOf(newParserEnd, baseStart);
const candStart = normalized.indexOf(newParserStart);
const candEnd = normalized.indexOf(newParserEnd, candStart);
assert(baseStart >= 0 && baseEnd > baseStart && candStart >= 0 && candEnd > candStart);
normalized = normalized.slice(0, candStart) + baseline.slice(baseStart, baseEnd) + normalized.slice(candEnd);
assert.equal(normalized, baseline);

console.log('PASS core-v0.11g-integration');
