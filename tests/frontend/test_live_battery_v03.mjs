import assert from "node:assert/strict";
import {batteryView, acDirectionText, batteryValue} from "../../frontend/live/state/battery-state.mjs";
import {readFileSync} from "node:fs";
const raw = {
  schema: "EMS_WEB_LIVE_BATTERY_V1", status: "FRESH", readOnly: true,
  eligibleForControl: false, eligibleForHouseBalance: false,
  ageSec: 75, sampledAtUtc: "2026-11-14T20:06:36Z",
  measurements: {socPct: 10.8, acPowerW: -13,
    chargeTotalKWh: 44.6, dischargeTotalKWh: 41.5}
};
assert.equal(batteryView(raw).socPct, 10.8);
assert.equal(batteryView(raw).acPowerW, -13);
assert.equal(acDirectionText(-13), "Rust / laag vermogen");
assert.match(acDirectionText(-800), /onbevestigd/);
assert.equal(acDirectionText(800), "Ontladen · indicatie");
assert.equal(batteryView({...raw, status: "STALE"}).acPowerW, null);
assert.equal(batteryView({...raw, eligibleForControl: true}).acPowerW, null);
assert.equal(batteryView({...raw, eligibleForHouseBalance: true}).acPowerW, null);
assert.equal(batteryValue(null, "kWh"), "—");
const html = readFileSync("frontend/live/index.html", "utf8");
const render = readFileSync("frontend/live/render/battery.mjs", "utf8");
const state = readFileSync("frontend/live/state/energy-state.js", "utf8");
for (const id of ["battery-soc","battery-ac-power","battery-charged","battery-discharged","battery-quality","battery-freshness"]) {
  assert.ok(html.includes('id="' + id + '"'));
  assert.ok(render.includes('"' + id + '"'));
}
assert.ok(html.includes('src="./render/battery.mjs"'));
assert.ok(render.includes('"/web/live/battery"'));
assert.ok(!state.includes("battery_alphaess"));
assert.ok(state.includes("pv + grid"));
console.log("PASS: AlphaESS Live V0.3 isolated rendering contract");
