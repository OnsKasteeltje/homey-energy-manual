import test from "node:test";
import assert from "node:assert/strict";
import { BC_STRATEGIES, replayBusinessCase, annualizeReplay, financialCase, compareBusinessCases } from "../docs/javascripts/business-case-engine-v2.js";

const scenario = {
  id: "TEST_10KWH",
  capacityKWh: 10,
  minSocPct: 20,
  maxSocPct: 90,
  initialSocPct: 50,
  maxChargeKW: 3,
  maxDischargeKW: 3,
  chargeEfficiency: 0.95,
  dischargeEfficiency: 0.95,
  standbyW: 0,
  capexEuro: 5000,
  lifetimeYears: 15,
  discountRate: 0.04,
  degradationEuroPerThroughputKWh: 0.02,
};

function s(gridW, importPrice=0.30, exportPrice=0.10, extra={}) {
  return { gridW, importPriceEuroPerKWh: importPrice, exportPriceEuroPerKWh: exportPrice, intervalMinutes: 60, measurementValid: true, ...extra };
}

test("baseline leaves grid energy unchanged", () => {
  const out = replayBusinessCase({ samples:[s(1000),s(-1000)], scenario, strategy:BC_STRATEGIES.BASELINE });
  assert.equal(out.energy.baselineImportKWh, 1);
  assert.equal(out.energy.importKWh, 1);
  assert.equal(out.energy.baselineExportKWh, 1);
  assert.equal(out.energy.exportKWh, 1);
  assert.equal(out.economics.grossOperationalSavingEuro, 0);
  assert.equal(out.controlImpact, false);
});

test("self-consumption stores export then avoids later import", () => {
  const out = replayBusinessCase({ samples:[s(-2000),s(1800)], scenario, strategy:BC_STRATEGIES.SELF_CONSUMPTION });
  assert.ok(out.energy.chargeAcKWh > 1.9);
  assert.ok(out.energy.dischargeAcKWh > 1.7);
  assert.ok(out.energy.exportKWh < out.energy.baselineExportKWh);
  assert.ok(out.energy.importKWh < out.energy.baselineImportKWh);
  assert.ok(out.economics.grossOperationalSavingEuro > 0);
});

test("SOC never leaves configured band", () => {
  const samples=[];
  for(let i=0;i<20;i++) samples.push(s(-10000));
  for(let i=0;i<20;i++) samples.push(s(10000));
  const out=replayBusinessCase({samples,scenario,strategy:BC_STRATEGIES.SELF_CONSUMPTION});
  for(const p of out.trace){assert.ok(p.socPct>=20-1e-6);assert.ok(p.socPct<=90+1e-6);}
});

test("EMS replay follows target but clamps physical power", () => {
  const out=replayBusinessCase({samples:[s(0,0.3,0.1,{emsBatteryTargetW:9000})],scenario,strategy:BC_STRATEGIES.EMS_REPLAY});
  assert.equal(out.trace[0].batteryAcW,3000);
});

test("invalid samples reduce evidence quality and are excluded", () => {
  const out=replayBusinessCase({samples:[s(1000),{gridW:null,importPriceEuroPerKWh:0.3,exportPriceEuroPerKWh:0.1}],scenario});
  assert.equal(out.evidence.validSamples,1);
  assert.equal(out.evidence.invalidSamples,1);
  assert.equal(out.evidence.quality,"LOW");
});

test("degradation is charged against throughput", () => {
  const out=replayBusinessCase({samples:[s(-2000),s(1800)],scenario,strategy:BC_STRATEGIES.SELF_CONSUMPTION});
  assert.ok(out.economics.degradationEuro>0);
  assert.ok(out.economics.netOperationalSavingEuro<out.economics.grossOperationalSavingEuro);
});

test("annualization warns on short evidence window", () => {
  const out=replayBusinessCase({samples:[s(-1000),s(1000)],scenario});
  const a=annualizeReplay(out,7);
  assert.equal(a.warning,"SHORT_EVIDENCE_WINDOW");
  assert.ok(a.annualizationFactor>50);
});

test("financial case returns payback and discounted NPV", () => {
  const f=financialCase({capexEuro:5000,annualNetSavingEuro:700,lifetimeYears:15,discountRate:0.04});
  assert.ok(f.simplePaybackYears>7 && f.simplePaybackYears<8);
  assert.ok(Number.isFinite(f.npvEuro));
});

test("capture ratio uses independently supplied oracle result", () => {
  const baseline={economics:{netOperationalSavingEuro:0}};
  const ems={economics:{netOperationalSavingEuro:80}};
  const oracle={economics:{netOperationalSavingEuro:100}};
  const c=compareBusinessCases({baseline,ems,oracle});
  assert.equal(c.emsCaptureRatio,0.8);
  assert.equal(c.emsGapToOracleEuro,20);
});
