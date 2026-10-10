import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";

// No browser or server required: the initial fetch remains unresolved.
const js=readFileSync("frontend/planner/render/planner.js","utf8");
const context={fetch:()=>new Promise(()=>{})};
vm.createContext(context);
vm.runInContext(js,context);
const choose=context.closestPlannerLine;
const slots=[
 {start:"t0",pvForecastW:600,evPlanW:0,quookerPlanW:0,gridImportAfterFlexW:200},
 {start:"t1",pvForecastW:600,evPlanW:0,quookerPlanW:1000,gridImportAfterFlexW:200},
 {start:"t2",pvForecastW:600,evPlanW:500,quookerPlanW:0,gridImportAfterFlexW:200},
];
const fields=[
 ["pvForecastW","pvline","PV voorspeld"],
 ["evPlanW","evline","Tesla gepland"],
 ["quookerPlanW","quookerline","Quooker gepland"],
 ["gridImportAfterFlexW","importline","Import verwacht"]
];
const xAt=i=>i*20;
const yAt=w=>100-w/20;
test("Quooker line hover selects only Quooker and matching quarter-hour",()=>{
 const hit=choose(slots,fields,20,50,xAt,yAt,8);
 assert.equal(hit.field,"quookerPlanW");
 assert.equal(hit.slot.start,"t1");
});
test("import and PV have independent hover targets",()=>{
 assert.equal(choose(slots,fields,20,90,xAt,yAt,6).field,"gridImportAfterFlexW");
 assert.equal(choose(slots,fields,20,70,xAt,yAt,6).field,"pvForecastW");
});
test("no tooltip between lines or outside the 96-slot axis",()=>{
 assert.equal(choose(slots,fields,20,35,xAt,yAt,5),null);
 assert.equal(choose(slots,fields,-20,70,xAt,yAt,10),null);
});
test("ambiguous overlapping zero-W lanes do not falsely identify a series",()=>{
 const zero=slots.map(s=>({...s,pvForecastW:0,evPlanW:0,quookerPlanW:0,gridImportAfterFlexW:0}));
 assert.equal(choose(zero,fields,20,100,xAt,yAt,8),null);
});
test("unknown planning values must not be replaced by zero-W evidence",()=>{
 const unknown=slots.map(s=>({...s,quookerPlanW:null}));
 assert.notEqual(choose(unknown,fields,20,50,xAt,yAt,5)?.field,"quookerPlanW");
});
