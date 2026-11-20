import assert from "node:assert/strict";
import {flowView} from "../../frontend/live/state/flow-v04.mjs";
import {batteryView, batteryFlowView} from "../../frontend/live/state/battery-state.mjs";
import {readFileSync} from "node:fs";
const measured = {p1Valid:true, grid:331, pvQuality:"MEASURED",pv:2800, house:3131, other:1900};
let f=flowView(measured);
assert.equal(f.gridPowerW,331);
assert.equal(f.gridArrow,"→");
assert.equal(f.gridDirection,"import");
assert.equal(f.pvPowerW,2800);
assert.equal(f.pvArrow,"→");
assert.equal(f.housePowerW,null); // 2800 + 331 includes unaccounted battery charging
assert.equal(f.otherPowerW,null);
f=flowView({...measured,grid:-1225});
assert.equal(f.gridDirection,"export");
assert.equal(f.gridArrow,"←");
assert.equal(f.gridPowerW,1225);
assert.equal(f.housePowerW,null);
f=flowView({...measured,p1Valid:false,grid:-1225});
assert.equal(f.gridPowerW,null);
assert.equal(f.gridDirection,"onbekend");
assert.equal(f.gridArrow,"↔");
f=flowView({...measured,pvQuality:"PARTIAL"});
assert.equal(f.pvPowerW,null);
assert.equal(f.pvArrow,"—");
assert.equal(f.housePowerW,null);
f=flowView({...measured,pvQuality:"MEASURED",pv:0,grid:0});
assert.equal(f.pvArrow,"—");
assert.equal(f.gridDirection,"in balans");
assert.equal(f.gridArrow,"↔");
f=flowView({});
assert.equal(f.gridPowerW,null);
assert.equal(f.housePowerW,null);
const battery = batteryView({
  schema:"EMS_WEB_LIVE_BATTERY_V1",status:"FRESH",readOnly:true,
  eligibleForControl:false,eligibleForHouseBalance:false,
  measurements:{socPct:12.8,acPowerW:-601,chargeTotalKWh:45.9,dischargeTotalKWh:42.3}
});
assert.equal(battery.acPowerW,-601);
assert.equal(batteryFlowView(battery).direction,"charging");
assert.equal(batteryFlowView(battery).arrow,"↓");
assert.match(batteryFlowView(battery).status,/indicatie/); // negative AC sign still unvalidated
const dischargeRaw = {
  schema:"EMS_WEB_LIVE_BATTERY_V1",status:"FRESH",readOnly:true,
  eligibleForControl:false,eligibleForHouseBalance:false,
  measurements:{acPowerW:800}
};
const discharge = batteryView(dischargeRaw);
assert.deepEqual(
  [batteryFlowView(discharge).direction,batteryFlowView(discharge).arrow,batteryFlowView(discharge).status],
  ["discharging","↑","Naar huis"]
);
const idle = batteryView({...dischargeRaw,measurements:{acPowerW:0}});
assert.equal(batteryFlowView(idle).direction,"idle");
assert.equal(batteryFlowView(idle).arrow,"—");
assert.equal(batteryFlowView({...discharge,status:"STALE"}).direction,"unknown");
assert.equal(batteryFlowView(batteryView({...dischargeRaw,eligibleForHouseBalance:true})).direction,"unknown");
assert.equal(batteryFlowView(batteryView({...dischargeRaw,measurements:{acPowerW:101}})).direction,"discharging");
assert.equal(batteryFlowView(batteryView({...dischargeRaw,measurements:{acPowerW:100}})).direction,"idle");
assert.equal(flowView(measured).housePowerW,null);
const html=readFileSync("frontend/live/index.html","utf8");
const js=readFileSync("frontend/live/render/live.js","utf8");
const batteryJs=readFileSync("frontend/live/render/battery.mjs","utf8");
const css=readFileSync("frontend/live/styles/live-v04.css","utf8");
const energyJs=readFileSync("frontend/live/state/energy-state.js","utf8");
for(const section of ['class="flow-card"','class="battery-panel"','class="loads-panel"','class="phases-panel"']) {
  assert.ok(html.includes(section),section);
}
for (const id of ["grid-power","grid-direction","grid-flow","pv-power","pv-flow","house-power","house-state",
 "other-power","tesla-power","heat-power","ww-flow-node","battery-flow-power",
 "battery-flow-link","battery-flow-status","battery-quality","battery-soc",
 "battery-ac-power","battery-charged","battery-discharged","battery-freshness",
 "loads-washer-status","loads-dryer-status","loads-dishwasher-status","loads-quooker-status",
 "loads-phase-l1","loads-phase-l2","loads-phase-l3","phases-net-power","phases-net-direction"]) {
  assert.ok(html.includes('id="' + id + '"'),id);
}
assert.ok(js.includes("flowView("));
assert.ok(js.includes("f.housePowerW"));
assert.ok(js.includes("f.otherPowerW"));
assert.ok(js.includes("f.gridDirection"));
assert.ok(batteryJs.includes('"battery-flow-power"'));
assert.ok(batteryJs.includes('"battery-flow-status"'));
assert.ok(batteryJs.includes("batteryFlowView(s)"));
assert.ok(batteryJs.includes("link.dataset.direction"));
assert.ok(!batteryJs.includes("eligibleForHouseBalance: true"));
assert.ok(energyJs.includes("pv + grid")); // existing module untouched; not used in V0.4 presentation
assert.ok(css.includes("grid-template-rows:minmax(0,1.26fr)"));
assert.ok(css.includes("@media (max-width:1050px)"));
assert.ok(css.includes("prefers-reduced-motion"));
assert.ok(!html.includes("1,2 kW"));
console.log("PASS: Live V0.4 one-screen flow and fail-closed bidirectional display contract");
