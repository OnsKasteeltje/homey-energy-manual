import assert from "node:assert/strict";
import {test} from "node:test";
import {diagnoseDishwasher} from "../../frontend/live/diagnostics/dishwasher-fingerprint.mjs";

const T0 = Date.parse("2026-10-14T06:15:00Z");
function snapshot(min, l1 = 100, opts = {}) {
  return {
    generatedAt: new Date(T0 + min * 60000).toISOString(),
    p1Valid: opts.p1Valid ?? true,
    gridPhases: [
      {name: "L1", power: l1}, {name: "L2", power: opts.l2 ?? 2300},
      {name: "L3", power: opts.l3 ?? 60}],
    teslaCharging: opts.tesla ?? false,
    tesla: opts.teslaPower ?? 0,
    loads: {
      washer:{active:opts.washer ?? true},
      dryer:{active:opts.dryer ?? false},
      quooker:{active:opts.quooker ?? false}
    }
  };
}
function run(sequence) {
  let history=[], result;
  for(const [minute, l1, opts] of sequence) {
    result=diagnoseDishwasher(snapshot(minute,l1,opts),history,T0 + minute * 60000);
    history=result.history;
  }
  return result;
}

test("washer L2 and dishwasher L1 can both be visible without a global block", () => {
  const r=run([[0,100],[5,1910],[10,1880],[15,390]]);
  assert.equal(r.status,"LIKELY");
  assert.equal(r.evidence.washerConfirmedL2,true);
  assert.equal(r.powerW,null);
  assert.equal(r.phase,"L1");
});

test("dryer active is not an automatic conflict, but phase uncertainty caps claim", () => {
  const r=run([[0,100,{dryer:true}],[5,1930,{dryer:true}],
    [10,1890,{dryer:true}],[15,350,{dryer:true}]]);
  assert.equal(r.status,"CANDIDATE");
  assert.equal(r.reason,"DRYER_PHASE_UNVERIFIED");
  assert.equal(r.powerW,null);
});

test("one kettle-like high sample is never a dishwasher detection", () => {
  const r=run([[0,100],[5,2000]]);
  assert.equal(r.status,"UNCONFIRMED");
  assert.equal(r.reason,"ISOLATED_L1_HIGH_LOAD");
});

test("L1 1.6 kW must have repeat evidence; not called a confirmed appliance", () => {
  const one=run([[0,100],[5,1681]]);
  assert.equal(one.status,"UNCONFIRMED");
  const two=run([[0,100],[5,1681],[10,1665]]);
  assert.equal(two.status,"CANDIDATE");
  assert.equal(two.confidence,0.50);
});

test("same source timestamp polled many times does not create fake corroboration", () => {
  const s=snapshot(5,1900);
  let hist=[];
  for(let i=0;i<20;i++) {
    const r=diagnoseDishwasher(s,hist,T0+5*60000 + i*15000);
    hist=r.history;
    assert.equal(r.status,"UNCONFIRMED");
  }
  assert.equal(hist.length,1);
});

test("fingerprint uses P1 alone, entirely independent of three inverters", () => {
  const values = [[0,100],[5,1900],[10,1920],[15,380]];
  const baseline=run(values);
  assert.equal(baseline.status,"LIKELY");
  let history = [], output;
  for (const [minute, l1] of values) {
    const s=snapshot(minute,l1);
    // The detector must not read any of these fields.
    s.pvSources = [
      {key:"solarEdge",power:100000,fresh:false},
      {key:"goodWe4200",power:20000,fresh:false},
      {key:"goodWe2000",power:40000,fresh:false}
    ];
    output=diagnoseDishwasher(s,history,T0+minute*60000);
    history=output.history;
  }
  assert.equal(output.status,baseline.status);
  assert.equal(output.confidence,baseline.confidence);
  assert.equal(output.signalW,380); // actual P1 L1, no inverter compensation
  assert.equal(output.source,"P1_NET_L1_FINGERPRINT");
  const p1=diagnoseDishwasher(snapshot(0,1800,{p1Valid:false}),[],T0);
  assert.equal(p1.status,"UNAVAILABLE");
  assert.equal(p1.reason,"P1_STALE");
});

test("negative P1 L1 export never counts as evidence of dishwasher ending", () => {
  const r=run([[0,100],[5,1900],[10,1920],[15,350],[20,-1100]]);
  assert.equal(r.status,"NO_MATCH");
  assert.notEqual(r.reason,"CYCLE_END_CONFIRMED");
});

test("new iPhone session uses Pi history rather than requiring browser-local samples", () => {
  const s=snapshot(15,390);
  s.sourceSampleAt = s.generatedAt;
  s.dishwasherL1History = [
    {ts:T0, signalW:100, excluded:false},
    {ts:T0+5*60000, signalW:1880, excluded:false},
    {ts:T0+10*60000, signalW:1920, excluded:false},
    {ts:T0+15*60000, signalW:390, excluded:false}
  ];
  const r=diagnoseDishwasher(s,[],T0+15*60000);
  assert.equal(r.status,"LIKELY");
  assert.equal(r.history.length,4);
  assert.equal(r.powerW,null);
});

test("short dishwasher low-load tail is retained, prolonged low ends cycle", () => {
  const tail=run([[0,100],[5,1900],[10,1920],[15,350],[20,100]]);
  assert.equal(tail.status,"CANDIDATE");
  assert.equal(tail.reason,"TAIL_AFTER_SEQUENCE");
  const ended=run([[0,100],[5,1900],[10,1920],[15,350],
                   [20,100],[25,105],[30,100]]);
  assert.equal(ended.status,"NO_MATCH");
  assert.equal(ended.reason,"CYCLE_END_CONFIRMED");
});

test("Tesla 3-phase overlap still suspends L1 fingerprint diagnosis", () => {
  const r=diagnoseDishwasher(snapshot(0,2000,{tesla:true}),[],T0);
  assert.equal(r.status,"SUSPENDED");
  assert.equal(r.reason,"TESLA_MULTIPHASE_INTERFERENCE");
  assert.equal(r.history[0].excluded,true);
});

test("stale, future and expired history cannot corroborate", () => {
  const stale=diagnoseDishwasher(snapshot(0,1900),[],T0+11*60000);
  assert.equal(stale.status,"UNAVAILABLE");
  const old=[{ts:T0-4*3600000,signalW:1900,excluded:false}];
  const r=diagnoseDishwasher(snapshot(0,2000),old,T0);
  assert.equal(r.status,"UNCONFIRMED");
  assert.equal(r.history.length,1);
});
