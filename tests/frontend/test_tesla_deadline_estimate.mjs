import assert from "node:assert/strict";
import {KWH_PER_SOC_PERCENT,estimateCharge,formatDuration,
  availableMinutesInAmsterdam,deadlineFeedback} from
  "../../frontend/settings/control/tesla-deadline-estimate.mjs";
import {readFileSync} from "node:fs";

const source=readFileSync(new URL("../../services/pi/api/status/tesla_command_ingest.py",import.meta.url),"utf8");
assert.match(source,/KWH_PER_SOC_PERCENT\s*=\s*0\.62\b/);
assert.equal(KWH_PER_SOC_PERCENT,0.62);

const ex=estimateCharge(40,60,10);
assert.equal(ex.kwh,12.4);
assert.equal(ex.minutes,108);
assert.equal(formatDuration(ex.minutes),"1 u 48 min");
assert.equal(ex.assumedAmps,false);
assert.equal(estimateCharge(40,60,6).minutes,180);
assert.equal(estimateCharge(40,60,16).minutes,68);
assert.equal(estimateCharge(40,60,NaN).amps,10);
assert.equal(estimateCharge(40,60,NaN).assumedAmps,true);
for(const args of [[40,40,10],[50,40,10],[99,100,10],[0,100,10],[40,60,17],[40,60,5],[40,60,10.5],[NaN,60,10]]){
  assert.equal(estimateCharge(...args),null,JSON.stringify(args));
}
const submitted=Date.parse("2026-10-09T20:43:45.483Z");
const available=availableMinutesInAmsterdam("2026-10-10T00:01",submitted);
assert.ok(Math.abs(available-77.24195)<0.001);
assert.equal(deadlineFeedback(ex,"2026-10-10T00:01",submitted).level,"warning");
assert.equal(deadlineFeedback(ex,"2026-10-10T02:00",submitted).level,"info");
assert.equal(deadlineFeedback(ex,"",submitted).level,"none");
assert.equal(availableMinutesInAmsterdam("2026-03-29T02:30",submitted),null); // spring gap
assert.equal(availableMinutesInAmsterdam("2026-10-25T02:30",submitted),null); // autumn fold
assert.equal(availableMinutesInAmsterdam("2026-02-31T10:00",submitted),null); // invalid

const html=readFileSync(new URL("../../frontend/settings/index.html",import.meta.url),"utf8");
const controller=readFileSync(new URL("../../frontend/settings/control/tesla-deadline.js",import.meta.url),"utf8");
for(const id of ["tesla-estimate-duration","tesla-estimate-details","tesla-estimate-feasibility"]){
  assert.ok(html.includes('id="'+id+'"'),id+" markup missing");
  assert.ok(controller.includes('"'+id+'"'),id+" controller missing");
}
assert.match(controller,/maxA:\$\("max-a"\)\?\.value\?\.trim\(\)===""\?NaN/);
assert.ok(controller.includes('renderEstimate();'));
assert.ok(controller.includes('"target-soc","deadline","max-a"'));
console.log("PASS: Tesla deadline duration, maxA, calibration and Amsterdam DST");
