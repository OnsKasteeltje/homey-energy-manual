import test from "node:test";
import assert from "node:assert/strict";
import { optimizePerfectInformation } from "../docs/javascripts/business-case-oracle-v0.1.js";
import { adaptEnergyHistory } from "../docs/javascripts/business-case-history-adapter-v0.1.js";

const scenario={id:"ORACLE_TEST",capacityKWh:4,minSocPct:0,maxSocPct:100,initialSocPct:0,maxChargeKW:2,maxDischargeKW:2,chargeEfficiency:1,dischargeEfficiency:1,standbyW:0,capexEuro:0,lifetimeYears:10,discountRate:0.04,degradationEuroPerThroughputKWh:0};
const sample=(gridW,price)=>({gridW,intervalMinutes:60,measurementValid:true,importPriceEuroPerKWh:price,exportPriceEuroPerKWh:0});

test("perfect-information oracle shifts energy from cheap to expensive interval",()=>{
  const out=optimizePerfectInformation({samples:[sample(1000,0.1),sample(1000,0.5)],scenario,energyStepKWh:1,terminalEnergyValueEuroPerKWh:0});
  assert.equal(out.perfectInformation,true);
  assert.ok(out.targetsW[0]>0);
  assert.ok(out.targetsW[1]<0);
  assert.ok(out.replay.economics.netOperationalSavingEuro>0);
});

test("oracle keeps same read-only boundary as replay",()=>{
  const out=optimizePerfectInformation({samples:[sample(0,0.1),sample(1000,0.5)],scenario,energyStepKWh:1,terminalEnergyValueEuroPerKWh:0});
  assert.equal(out.readOnly,true);assert.equal(out.controlImpact,false);assert.equal(out.replay.controlImpact,false);
});

test("history adapter preserves P1 sign and explicit fixed tariffs",()=>{
  const history={schema_version:"2.4",date_local:"2026-08-26",sample_interval_minutes:5,samples:[{ts:"x",p1W:-500,p1Valid:true,revision:1,solarEdgeW:1000,goodWe4200W:500,goodWe2000W:0}]};
  const out=adaptEnergyHistory({history,fixedImportPriceEuroPerKWh:0.3,fixedExportPriceEuroPerKWh:0.1});
  assert.equal(out.samples[0].gridW,-500);
  assert.equal(out.samples[0].importPriceEuroPerKWh,0.3);
  assert.equal(out.samples[0].exportPriceEuroPerKWh,0.1);
  assert.equal(out.samples[0].evidence.pvW,1500);
});

test("history adapter does not turn invalid P1 into zero",()=>{
  const history={samples:[{p1W:null,p1Valid:false}]};
  const out=adaptEnergyHistory({history,fixedImportPriceEuroPerKWh:0.3,fixedExportPriceEuroPerKWh:0.1});
  assert.equal(out.samples[0].gridW,null);assert.equal(out.samples[0].measurementValid,false);
});
