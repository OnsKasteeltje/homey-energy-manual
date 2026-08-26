import test from 'node:test';
import assert from 'node:assert/strict';
import {createContractHistoryTariffResolver} from '../docs/javascripts/business-case-tariff-resolver-v0.1.js';
import {resolveScenarioCapex,applyCompleteCapex} from '../docs/javascripts/business-case-capex-v0.1.js';
import {calibrateVictronTelemetry,calibrationCandidateForScenario} from '../docs/javascripts/business-case-victron-calibration-v0.1.js';
import {replayBusinessCase,BC_STRATEGIES} from '../docs/javascripts/business-case-engine-v2.js';

const scenario={id:'T',capacityKWh:10,minSocPct:20,maxSocPct:90,initialSocPct:50,maxChargeKW:3,maxDischargeKW:3,chargeEfficiency:.95,dischargeEfficiency:.95,standbyW:0,capexEuro:null,lifetimeYears:15,discountRate:.04,degradationEuroPerThroughputKWh:.02};

test('tariff resolver never looks into the future and uses latest GOOD history row',()=>{
  const resolve=createContractHistoryTariffResolver({contractHistory:[
    {ts:'2026-08-26T10:00:00Z',contractType:'FIXED',price:{quality:'GOOD',importNow:.24,exportNow:.15,source:'FIXED'}},
    {ts:'2026-08-26T10:15:00Z',contractType:'FIXED',price:{quality:'GOOD',importNow:.25,exportNow:.15,source:'FIXED'}}
  ]});
  const a=resolve({ts:'2026-08-26T10:14:59Z'}); assert.equal(a.importPriceEuroPerKWh,.24); assert.equal(a.tariffSource,'CONTRACT_HISTORY');
  const b=resolve({ts:'2026-08-26T10:16:00Z'}); assert.equal(b.importPriceEuroPerKWh,.25);
});

test('tariff resolver rejects stale history and marks explicit fallback',()=>{
  const resolve=createContractHistoryTariffResolver({contractHistory:[{ts:'2026-08-26T10:00:00Z',price:{quality:'GOOD',importNow:.2,exportNow:.1}}],maxAgeMinutes:30,fallback:{contractType:'FIXED',importPriceEuroPerKWh:.2379,exportPriceEuroPerKWh:.15}});
  const out=resolve({ts:'2026-08-26T11:00:00Z'}); assert.equal(out.tariffSource,'EXPLICIT_FALLBACK'); assert.equal(out.quality,'FALLBACK');
});

test('operational replay remains valid with CAPEX intentionally null',()=>{
  const out=replayBusinessCase({samples:[{ts:'2026-08-26T10:00:00Z',gridW:1000,p1Valid:true,importPriceEuroPerKWh:.24,exportPriceEuroPerKWh:.15,intervalMinutes:5}],scenario,strategy:BC_STRATEGIES.BASELINE});
  assert.equal(out.readOnly,true); assert.equal(out.controlImpact,false); assert.equal(out.evidence.validSamples,1);
});

test('CAPEX gate exposes known hardware subtotal but blocks financial case until complete',()=>{
  const evidence={scenarios:{T:{knownIncrementalHardwareEuro:2500,completeCapexEuro:null,completeness:'PARTIAL'}}};
  const r=resolveScenarioCapex({capexEvidence:evidence,scenarioId:'T'}); assert.equal(r.financialReady,false); assert.equal(r.knownIncrementalHardwareEuro,2500);
  assert.equal(applyCompleteCapex(scenario,r).capexEuro,null);
});

test('Victron calibration derives efficiencies only from sufficient closed-cycle evidence',()=>{
  const samples=[]; let t=Date.parse('2026-08-26T00:00:00Z');
  for(let i=0;i<12;i++){samples.push({ts:new Date(t).toISOString(),valid:true,batteryAcW:2000,batteryDcW:1900,socPct:50+i*.5,systemLossW:20});t+=15*60_000;}
  for(let i=0;i<12;i++){samples.push({ts:new Date(t).toISOString(),valid:true,batteryAcW:-1805,batteryDcW:-1900,socPct:56-i*.5,systemLossW:20});t+=15*60_000;}
  const out=calibrateVictronTelemetry({samples,usableCapacityKWh:7,minThroughputKWh:1});
  assert.ok(out.metrics.chargeEfficiency>0.94&&out.metrics.chargeEfficiency<0.96);
  assert.ok(out.metrics.dischargeEfficiency>0.94&&out.metrics.dischargeEfficiency<0.96);
  assert.equal(out.readOnly,true); assert.equal(out.controlImpact,false);
});

test('low-quality calibration is never auto-promotable',()=>{
  const cal=calibrateVictronTelemetry({samples:[{ts:'2026-08-26T00:00:00Z',valid:true,batteryAcW:0,socPct:50,intervalMinutes:5}],usableCapacityKWh:7});
  const candidate=calibrationCandidateForScenario({scenario,calibration:cal}); assert.equal(candidate.promotable,false); assert.equal(candidate.candidate,null);
});
