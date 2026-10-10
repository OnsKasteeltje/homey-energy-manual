import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";

const script=readFileSync("frontend/pv-flex/render/pv-flex.js","utf8");
// Execute only pure read-only view helpers: no browser, server, or physical writes.
const pure=script.slice(script.indexOf("const available="),script.indexOf("function summary(d)"));
const picker=script.slice(script.indexOf("function closestEvaluationSeries("),script.indexOf("function chart(d)"));
const scope={};
vm.createContext(scope);
vm.runInContext(pure+picker,scope);
const evidence=(s,now)=>vm.runInContext("slotEvidence",scope)(s,now);
const hover=vm.runInContext("closestEvaluationSeries",scope);
const start="2026-10-10T08:30:00Z",end="2026-10-10T08:45:00Z";
const plan={evPlanW:0,wwPlanW:0,quookerPlanW:0};
function slot(extra={}){
 return {start,end,actual:{p1Coverage:1,pvCoverage:1,pvKWh:.1,importKWh:.05,exportKWh:.01},forecast:{pvForecastW:400},plan,...extra};
}
test("running quarter is provisional even if device power was already recorded",()=>{
 const result=evidence(slot(),Date.parse("2026-10-10T08:36:00Z"));
 assert.equal(result.phase,"OPEN");
 assert.equal(result.comparable,false);
 assert.equal(result.p1,false);
 assert.equal(result.pv,false);
});
test("0% coverage is not an actual measured zero",()=>{
 const s=slot({actual:{p1Coverage:0,pvCoverage:0,pvKWh:0,importKWh:0,exportKWh:0}});
 const q=evidence(s,Date.parse("2026-10-10T08:50:00Z"));
 assert.equal(q.phase,"CLOSED");
 assert.equal(q.comparable,false);
 assert.equal(q.p1,false);
 assert.equal(q.pv,false);
});
test("partial or unknown P1/PV coverage does not get a complete outcome",()=>{
 for(const actual of [
  {p1Coverage:.94,pvCoverage:1,pvKWh:1,importKWh:0,exportKWh:0},
  {p1Coverage:1,pvCoverage:.5,pvKWh:1,importKWh:0,exportKWh:0},
  {p1Coverage:1,pvCoverage:1,pvKWh:null,importKWh:0,exportKWh:0}
 ]){
  assert.equal(evidence(slot({actual}),Date.parse("2026-10-10T08:50:00Z")).comparable,false);
 }
});
test("only a closed quarter with original plan and independent measured P1/PV is comparable",()=>{
 const now=Date.parse("2026-10-10T08:50:00Z");
 assert.equal(evidence(slot(),now).comparable,true);
 assert.equal(evidence(slot({plan:null}),now).comparable,false);
 assert.equal(evidence(slot({forecast:null}),now).comparable,false);
});
test("hover selects only the nearest nonzero PV/EV/Quooker line",()=>{
 const slots=[
  slot({forecast:{pvForecastW:400},plan:{evPlanW:0,wwPlanW:0,quookerPlanW:0}}),
  slot({forecast:{pvForecastW:400},plan:{evPlanW:0,wwPlanW:0,quookerPlanW:1000}}),
  slot({forecast:{pvForecastW:400},plan:{evPlanW:0,wwPlanW:0,quookerPlanW:0}})
 ];
 const empty=slots.map(()=>({pvW:0,evPvW:0,otherPvW:0,exportW:0,actualKnown:false}));
 const view={left:0,top:0,height:100,step:20,max:1000,radius:6};
 const quooker=hover(slots,empty,1,30,0,view);
 assert.equal(quooker.label,"Quooker gepland");
 assert.equal(quooker.value,1000);
 const pv=hover(slots,empty,1,30,60,view);
 assert.equal(pv.label,"PV-forecast bij besluit");
 assert.equal(hover(slots,empty,1,30,32,view),null);
});
test("hover on a stacked measured PV bar reports only that component",()=>{
 const slots=[slot(),slot(),slot()];
 const bars=slots.map(()=>({actualKnown:true,pvW:500,evPvW:100,otherPvW:300,exportW:100}));
 const view={left:0,top:0,height:100,step:20,max:1000,radius:4};
 const bar=hover(slots,bars,1,30,80,view);
 assert.equal(bar.label,"Overig eigen PV");
 assert.equal(bar.value,300);
});
test("mousemove must not choose a historical decision",()=>{
 const mouse=script.split('hit.addEventListener("mousemove",event=>')[1].split('hit.addEventListener("mouseleave"')[0];
 assert.ok(mouse.includes("closestEvaluationSeries"));
 assert.ok(!mouse.includes("renderEvidence("));
 assert.ok(script.includes('hit.addEventListener("click",()=>'));
 assert.ok(script.includes("renderEvidence(slot,Date.now())"));
});
