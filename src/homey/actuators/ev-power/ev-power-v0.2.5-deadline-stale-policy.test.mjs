import assert from 'node:assert/strict';

const allowStaleStateDeadline = ({
  deadlineGuardApplied,
  evStatus,
  evSource,
  targetW,
  requestedA,
  remainingKWh,
  deadlineAtMs,
  nowMs,
}) => deadlineGuardApplied === true
  && evStatus === 'NUMERIC_DEADLINE_TARGET'
  && evSource === 'REMAINING_KWH_OVER_TIME_TO_DEADLINE'
  && targetW > 0
  && Number.isInteger(requestedA)
  && requestedA >= 7
  && remainingKWh > 0
  && Number.isFinite(deadlineAtMs)
  && deadlineAtMs > nowMs;

const now = Date.parse('2026-09-13T20:45:00.000Z');
const base = {
  deadlineGuardApplied: true,
  evStatus: 'NUMERIC_DEADLINE_TARGET',
  evSource: 'REMAINING_KWH_OVER_TIME_TO_DEADLINE',
  targetW: 11040,
  requestedA: 16,
  remainingKWh: 7.7,
  deadlineAtMs: Date.parse('2026-09-13T21:30:00.000Z'),
  nowMs: now,
};

assert.equal(allowStaleStateDeadline(base), true, 'active validated deadline may continue with stale state telemetry');
assert.equal(allowStaleStateDeadline({...base, deadlineGuardApplied:false}), false, 'ordinary opportunity charging must not bypass stale state');
assert.equal(allowStaleStateDeadline({...base, evStatus:'NUMERIC_REALTIME_PV_TARGET'}), false, 'PV target must not bypass stale state');
assert.equal(allowStaleStateDeadline({...base, evSource:'HOMEY_BOUNDED_REALTIME_PV'}), false, 'non-deadline source must not bypass stale state');
assert.equal(allowStaleStateDeadline({...base, requestedA:0}), false, 'zero-current intent does not need or receive override');
assert.equal(allowStaleStateDeadline({...base, remainingKWh:0}), false, 'completed deadline does not bypass stale state');
assert.equal(allowStaleStateDeadline({...base, deadlineAtMs:now}), false, 'expired deadline does not bypass stale state');

const controlFresh = ({intentAge, adapterAge, gateAge, maxAge=120000}) =>
  intentAge >= 0 && intentAge <= maxAge
  && adapterAge >= 0 && adapterAge <= maxAge
  && gateAge >= 0 && gateAge <= maxAge;

assert.equal(controlFresh({intentAge:1000,adapterAge:1000,gateAge:1000}), true);
assert.equal(controlFresh({intentAge:121000,adapterAge:1000,gateAge:1000}), false, 'stale intent remains hard fail');
assert.equal(controlFresh({intentAge:1000,adapterAge:121000,gateAge:1000}), false, 'stale adapter remains hard fail');
assert.equal(controlFresh({intentAge:1000,adapterAge:1000,gateAge:121000}), false, 'stale gate remains hard fail');

console.log('PASS ev-power v0.2.5 stale-state deadline policy');
