// Focused regression for GitHub #38. No Homey/device calls, no writes.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const source = readFileSync('src/homey/core/core-v0.11p.candidate-homey.js', 'utf8');
const AsyncFunction = Object.getPrototypeOf(async function() {}).constructor;
new AsyncFunction(source); // The deployed HomeyScript must be syntactically valid.
assert(source.includes('quattWritePerformed:false,goalLatchPreserved:true'));
assert(!source.includes('quattWritePerformed:falsegoalLatchPreserved:true'));

const begin = source.indexOf('if(heatingNow){st.heatingConfirmMin=');
const end = source.indexOf('const goalReachedToday=', begin);
assert(begin >= 0 && end > begin, 'WW low-power Core block missing');
const runBlock = new Function('st', 'state', 'heatingNow', 'deltaMin', 'boilerOn', 'powerW', 'today',
  source.slice(begin, end) + '\nreturn st;');

function scenario({legacyMinutes=0, confirmed=true}={}) {
  const st = {heatingConfirmMin: 15, heatingConfirmed: confirmed,
    lowAfterHeatingMin: legacyMinutes, goalReachedToday: false,
    lastStateSampleAt: '2026-08-30T14:40:00.000Z'};
  function tick(utcMinute, powerW, boilerOn=true) {
    const sampledAt = utcMinute + ':00.000Z';
    runBlock(st, {sampledAt}, boilerOn && powerW > 1500, 5, boilerOn, powerW, '2026-08-30');
    st.lastStateSampleAt = sampledAt; // What the Core persists on every tick.
    return {...st};
  }
  return {tick, st};
}

// Thermostat physically drops between 14:40 and 14:45. First *observed*
// low-power sample is 14:45; a subsequent 14:50 tick must not latch.
{
  const s = scenario();
  assert.equal(s.tick('2026-08-30T14:45', 0).lowAfterHeatingMin, 0);
  const five = s.tick('2026-08-30T14:50', 0);
  assert.equal(five.lowAfterHeatingMin, 5);
  assert.equal(five.goalReachedToday, false);
  const ten = s.tick('2026-08-30T14:55', 0);
  assert.equal(ten.lowAfterHeatingMin, 10);
  assert.equal(ten.goalReachedToday, true);
  assert.equal(ten.goalLatchDate, '2026-08-30');
}

// Power >= 100 W and switch OFF reset evidence; low-power cannot resume
// an old, partly elapsed 10-minute confirmation window.
{
  const s = scenario();
  s.tick('2026-08-30T14:45', 0);
  s.tick('2026-08-30T14:50', 0);
  assert.equal(s.tick('2026-08-30T14:52', 100).lowAfterHeatingStartedAt, null);
  assert.equal(s.tick('2026-08-30T14:54', 0).lowAfterHeatingMin, 0);
  assert.equal(s.tick('2026-08-30T14:56', 0, false).lowAfterHeatingMin, 0);
  assert.equal(s.tick('2026-08-30T14:58', 0).lowAfterHeatingMin, 0);
  assert.equal(s.st.goalReachedToday, false);
}

// A skipped/stale Core observation (>5 minutes at a 2-minute cadence)
// cannot silently count as uninterrupted low power.
{
  const s = scenario();
  s.tick('2026-08-30T14:45', 0);
  const afterGap = s.tick('2026-08-30T14:57', 0);
  assert.equal(afterGap.lowAfterHeatingMin, 0);
  assert.equal(afterGap.goalReachedToday, false);
}

// Existing legacy minutes are not grandfathered into a valid start timestamp.
{
  const s = scenario({legacyMinutes: 9});
  const first = s.tick('2026-08-30T14:45', 0);
  assert.equal(first.lowAfterHeatingMin, 0);
  assert.equal(first.goalReachedToday, false);
}
console.log('PASS: WW low-power confirmation uses first observed low timestamp');
