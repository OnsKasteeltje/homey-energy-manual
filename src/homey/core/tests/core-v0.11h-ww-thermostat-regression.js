'use strict';

// PREP ONLY / NOT DEPLOYED
// Pure offline policy regression model for the surgical v0.11h WW change.
// This does NOT call Homey, devices, Logic, GitHub, or network APIs.

const LOW_W = 100;
const MAX_IMPORT_W = 4000;

function evaluate(input) {
  const {
    boilerOn = true,
    powerW = 0,
    runLocked = false,
    prevVerifyActive = false,
    verifyAgeMin = 0,
    mode = true,
    before19 = true,
    goalReachedToday = false,
    heatingConfirmed = true,
    catchupRequired = false,
    p1Fresh = true,
    gridMeasurementValid = true,
    importW = 0,
    opportunity = false,
    expensive = false,
    plannerStarted = false,
    plannerOpportunity = false,
  } = input;

  if (!mode) return ['BOILER_OFF', 'BLOCKED_MODE'];
  if (!before19) return ['BOILER_OFF', 'AFTER_DEADLINE'];
  if (goalReachedToday) return ['BOILER_OFF', 'GOAL_REACHED_END_MANDATORY'];
  if (catchupRequired) return ['HOLD', 'CATCHUP'];
  if (runLocked) return ['HOLD', 'RUN_LOCK'];

  const verifyImportSafe = importW <= MAX_IMPORT_W;
  const verifyLowPower = boilerOn && powerW < LOW_W;
  const plannerStop = boilerOn && plannerStarted && !plannerOpportunity;
  const importOrPriceStop = boilerOn && !opportunity && (expensive || importW > 500);
  const verifyRequested = plannerStop || importOrPriceStop;
  const verifyBaseEligible = mode && before19 && !goalReachedToday && boilerOn &&
    heatingConfirmed && verifyLowPower && !catchupRequired && p1Fresh &&
    gridMeasurementValid && verifyImportSafe;

  if (boilerOn && prevVerifyActive && (!p1Fresh || !gridMeasurementValid || !verifyImportSafe || !verifyLowPower)) {
    return ['BOILER_OFF', 'THERMOSTAT_VERIFY_ABORT'];
  }
  if (boilerOn && prevVerifyActive && verifyAgeMin >= 20) {
    return ['BOILER_OFF', 'THERMOSTAT_VERIFY_EXPIRED_OFF'];
  }
  if (boilerOn && verifyRequested && verifyBaseEligible && (!prevVerifyActive || verifyAgeMin < 20)) {
    return ['HOLD', 'THERMOSTAT_VERIFY'];
  }
  if (boilerOn && plannerStarted && !plannerOpportunity) return ['BOILER_OFF', 'PLANNER_SLOT_END'];
  if (boilerOn && !opportunity && (expensive || importW > 500)) return ['BOILER_OFF', expensive ? 'WAIT_PRICE' : 'WAIT_IMPORT'];
  return ['HOLD', 'HOLD_RUN'];
}

const cases = [
  {
    name: '2026-09-02 incident: high-power boiler + 900 W import after lock',
    input: { powerW: 1954, importW: 900, opportunity: false, runLocked: false, heatingConfirmed: true },
    expected: ['BOILER_OFF', 'WAIT_IMPORT'],
  },
  {
    name: 'minimum PV run-lock remains intact',
    input: { powerW: 1954, importW: 900, opportunity: false, runLocked: true, heatingConfirmed: true },
    expected: ['HOLD', 'RUN_LOCK'],
  },
  {
    name: 'low-power thermostat evidence may start verification',
    input: { powerW: 42, importW: 900, opportunity: false, runLocked: false, heatingConfirmed: true },
    expected: ['HOLD', 'THERMOSTAT_VERIFY'],
  },
  {
    name: 'active verification aborts if element resumes heating',
    input: { powerW: 1900, importW: 900, opportunity: false, prevVerifyActive: true, verifyAgeMin: 5 },
    expected: ['BOILER_OFF', 'THERMOSTAT_VERIFY_ABORT'],
  },
  {
    name: 'active low-power verification can continue below 20 min',
    input: { powerW: 35, importW: 900, opportunity: false, prevVerifyActive: true, verifyAgeMin: 5 },
    expected: ['HOLD', 'THERMOSTAT_VERIFY'],
  },
  {
    name: 'verification still expires at 20 min',
    input: { powerW: 35, importW: 900, opportunity: false, prevVerifyActive: true, verifyAgeMin: 20 },
    expected: ['BOILER_OFF', 'THERMOSTAT_VERIFY_EXPIRED_OFF'],
  },
  {
    name: 'planner high-power stop is not masked by verification',
    input: { powerW: 1900, importW: 100, plannerStarted: true, plannerOpportunity: false, opportunity: false },
    expected: ['BOILER_OFF', 'PLANNER_SLOT_END'],
  },
  {
    name: 'catch-up semantics remain higher priority',
    input: { powerW: 1900, importW: 900, catchupRequired: true },
    expected: ['HOLD', 'CATCHUP'],
  },
  {
    name: 'mode-off remains hard off',
    input: { powerW: 1900, importW: 0, mode: false },
    expected: ['BOILER_OFF', 'BLOCKED_MODE'],
  },
  {
    name: 'after 19:00 remains hard off',
    input: { powerW: 1900, importW: 0, before19: false },
    expected: ['BOILER_OFF', 'AFTER_DEADLINE'],
  },
];

let failures = 0;
for (const c of cases) {
  const actual = evaluate(c.input);
  const pass = JSON.stringify(actual) === JSON.stringify(c.expected);
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${c.name} | ${actual.join(' / ')}`);
  if (!pass) failures++;
}
if (failures) process.exitCode = 1;
else console.log(`PASS | ${cases.length}/${cases.length} regression cases`);
