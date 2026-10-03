import test from 'node:test';
import assert from 'node:assert/strict';

import {
  CONFIG,
  appendAvailableSample,
  evaluateEvPhaseCurrentCandidate,
  reconstructAvailableTotalW,
  rollingAvailable,
  wattsPerAmp,
} from '../src/homey/ev/ev-phase-current-controller-v0.2.mjs';

const NOW = 1_800_000_000_000;

function samples(w, now = NOW) {
  return [
    {atMs: now - 120000, w},
    {atMs: now - 60000, w},
  ];
}

function previous(mode, requestedA, {
  modeAgeMs = 600000,
  availableW = 2500,
  upscaleAgeMs = null,
} = {}) {
  return {
    mode,
    modeSinceMs: NOW - modeAgeMs,
    requestedA,
    upscaleSinceMs: upscaleAgeMs === null ? null : NOW - upscaleAgeMs,
    availableSamples: samples(availableW),
  };
}

function inputForAvailable(availableW, extra = {}) {
  return {
    opportunityAllowed: true,
    deadlineActive: false,
    p1Fresh: true,
    evActualFresh: true,
    p1W: -availableW,
    evActualW: 0,
    maxA: 16,
    ...extra,
  };
}

test('reconstructs counterfactual EV-available power from P1 plus actual EV load', () => {
  assert.equal(reconstructAvailableTotalW({p1W: -2500, evActualW: 0}), 2500);
  assert.equal(reconstructAvailableTotalW({p1W: 1640, evActualW: 4140}), 2500);
  assert.equal(reconstructAvailableTotalW({p1W: 500, evActualW: 0}), 0);
});

test('rolling signal is time-weighted across the trailing 120 seconds', () => {
  const s = [
    {atMs: NOW - 120000, w: 1000},
    {atMs: NOW - 60000, w: 3000},
    {atMs: NOW, w: 3000},
  ];
  const r = rollingAvailable(s, NOW);
  assert.equal(Math.round(r.avgW), 2000);
  assert.equal(r.ready, true);
  assert.ok(r.coverageMs >= CONFIG.rollingMinCoverageMs);
});

test('unknown OFF modeSince does not create an artificial 300 s startup dwell', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(1700),
    {
      mode: 'OFF',
      requestedA: 0,
      modeSinceMs: null,
      availableSamples: samples(1700),
    },
    NOW,
  );
  assert.equal(r.upwardModeDwellOK, true);
  assert.equal(r.mode, '1P');
  assert.equal(r.phaseReason, 'OFF_TO_1P_ROLLING_HIGH');
});

test('OFF -> 1P requires sustained rolling surplus and sizes current in 1P', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(1700),
    previous('OFF', 0, {availableW: 1700}),
    NOW,
  );
  assert.equal(r.mode, '1P');
  assert.equal(r.phaseReason, 'OFF_TO_1P_ROLLING_HIGH');
  assert.equal(r.requestedA, 8);
  assert.equal(r.requestedW, 8 * 230);
  assert.equal(r.mappingWPerA, 230);
  assert.equal(r.requiresPhysicalPhaseTransition, true);
});

test('OFF -> 3P entry respects the +200 W import target', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(4600),
    previous('OFF', 0, {availableW: 4600}),
    NOW,
  );
  assert.equal(r.mode, '3P');
  assert.equal(r.phaseReason, 'OFF_TO_3P_ROLLING_HIGH');
  assert.equal(r.requestedA, 6);
  assert.equal(r.requestedW, 6 * 690);
  assert.equal(r.syntheticP1W, -460);
  assert.equal(r.mappingWPerA, 690);
});


test('high rolling surplus does not force phase entry when instantaneous power cannot sustain 6 A', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(1000),
    previous('OFF', 0, {
      modeAgeMs: 600000,
      availableW: 5000,
    }),
    NOW,
  );
  assert.equal(r.rollingReady, true);
  assert.equal(r.mode, 'OFF');
  assert.equal(r.phaseChanged, false);
});

test('upward 1P -> 3P transition is blocked before 300 s dwell', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(5000),
    previous('1P', 16, {
      modeAgeMs: 120000,
      availableW: 5000,
    }),
    NOW,
  );
  assert.equal(r.mode, '1P');
  assert.equal(r.phaseChanged, false);
  assert.equal(r.upwardModeDwellOK, false);
});

test('upward 1P -> 3P occurs after 300 s dwell on sustained rolling surplus', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(5000),
    previous('1P', 16, {
      modeAgeMs: 360000,
      availableW: 5000,
    }),
    NOW,
  );
  assert.equal(r.mode, '3P');
  assert.equal(r.phaseReason, '1P_TO_3P_ROLLING_HIGH');
  assert.equal(r.phaseChanged, true);
});

test('sustained 3P -> 1P downshift is not trapped by upward dwell', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(3000),
    previous('3P', 6, {
      modeAgeMs: 60000,
      availableW: 3000,
    }),
    NOW,
  );
  assert.equal(r.mode, '1P');
  assert.equal(r.phaseReason, '3P_TO_1P_ROLLING_LOW');
  assert.equal(r.phaseChanged, true);
});

test('sustained 1P -> OFF stop is not trapped by upward dwell', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(900),
    previous('1P', 6, {
      modeAgeMs: 60000,
      availableW: 900,
    }),
    NOW,
  );
  assert.equal(r.mode, 'OFF');
  assert.equal(r.requestedA, 0);
  assert.equal(r.phaseReason, '1P_TO_OFF_ROLLING_LOW');
});

test('OFF re-entry waits for 300 s after a recent stop', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(2500),
    previous('OFF', 0, {
      modeAgeMs: 120000,
      availableW: 2500,
    }),
    NOW,
  );
  assert.equal(r.mode, 'OFF');
  assert.equal(r.phaseChanged, false);
  assert.equal(r.upwardModeDwellOK, false);
});

test('1P current regulator performs proportional fast down-regulation', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(2000),
    previous('1P', 12, {availableW: 2000}),
    NOW,
  );
  assert.equal(r.mode, '1P');
  assert.equal(r.requestedA, 9);
  assert.equal(r.currentReason, 'FAST_IMPORT_DOWN');
  assert.equal(r.phaseChanged, false);
  assert.equal(r.currentOnlyChange, true);
});

test('3P current regulator performs proportional fast down-regulation', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(5000),
    previous('3P', 10, {availableW: 5000}),
    NOW,
  );
  assert.equal(r.mode, '3P');
  assert.equal(r.requestedA, 7);
  assert.equal(r.currentReason, 'FAST_IMPORT_DOWN');
  assert.equal(r.phaseChanged, false);
  assert.equal(r.currentOnlyChange, true);
});

test('1P predictive regulator jumps by at most 3 A toward calculated target', () => {
  // 10 A physical load + 1270 W export => ~3570 W available.
  // With +200 W import allowance the calculated target is 16 A.
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(3570, {physicalA: 10}),
    previous('1P', 10, {availableW: 3570}),
    NOW,
  );
  assert.equal(r.mode, '1P');
  assert.equal(r.desiredA, 16);
  assert.equal(r.requestedA, 13);
  assert.equal(r.currentReason, 'PREDICTIVE_UP_BOUNDED');
  assert.equal(r.physicalTargetSettled, true);
  assert.equal(r.requiresPhysicalPhaseTransition, false);
});

test('1P predictive regulator waits for Easee to reach previous target before another jump', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(3570, {physicalA: 10}),
    previous('1P', 13, {availableW: 3570}),
    NOW,
  );
  assert.equal(r.desiredA, 16);
  assert.equal(r.requestedA, 13);
  assert.equal(r.currentReason, 'PREDICTIVE_UP_WAIT_PHYSICAL');
  assert.equal(r.physicalTargetSettled, false);
});

test('1P predictive regulator can complete second bounded jump after physical confirmation', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(3570, {physicalA: 13}),
    previous('1P', 13, {availableW: 3570}),
    NOW,
  );
  assert.equal(r.desiredA, 16);
  assert.equal(r.requestedA, 16);
  assert.equal(r.currentReason, 'PREDICTIVE_UP_BOUNDED');
});

test('3P predictive regulator jumps by at most 2 A toward calculated target', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(6200, {physicalA: 6}),
    previous('3P', 6, {availableW: 6200}),
    NOW,
  );
  assert.equal(r.mode, '3P');
  assert.equal(r.desiredA, 9);
  assert.equal(r.requestedA, 8);
  assert.equal(r.currentReason, 'PREDICTIVE_UP_BOUNDED');
  assert.equal(r.requiresPhysicalPhaseTransition, false);
});

test('3P predictive upscale accepts about 200 W predicted import instead of leaving 500-600 W export', () => {
  // 7 A * 690 W + 550 W export = 5380 W available.
  // 8 A then predicts 5520 - 5380 = 140 W grid import.
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(5380, {physicalA: 7}),
    previous('3P', 7, {availableW: 5380}),
    NOW,
  );
  assert.equal(r.mode, '3P');
  assert.equal(r.desiredA, 8);
  assert.equal(r.requestedA, 8);
  assert.equal(r.currentReason, 'PREDICTIVE_UP_BOUNDED');
  assert.equal(r.syntheticP1W, 140);
});

test('3P predictive controller holds when next amp would exceed 200 W import target', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(5280, {physicalA: 7}),
    previous('3P', 7, {availableW: 5280}),
    NOW,
  );
  assert.equal(r.desiredA, 7);
  assert.equal(r.requestedA, 7);
  assert.equal(r.currentReason, 'HOLD_A');
});

test('same-phase A change never requests a physical phase transition', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(2000),
    previous('1P', 12, {availableW: 2000}),
    NOW,
  );
  assert.equal(r.phaseChanged, false);
  assert.equal(r.currentChanged, true);
  assert.equal(r.currentOnlyChange, true);
  assert.equal(r.requiresPhysicalPhaseTransition, false);
});

test('envelope maxA reduction is applied immediately without phase switch', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(3000, {maxA: 8}),
    previous('1P', 12, {availableW: 3000}),
    NOW,
  );
  assert.equal(r.mode, '1P');
  assert.equal(r.requestedA, 8);
  assert.equal(r.currentReason, 'ENVELOPE_CAP_DOWN');
  assert.equal(r.phaseChanged, false);
});


test('active deadline before force still allows opportunity control', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(2500, {deadlineActive: true, deadlineForceActive: false}),
    previous('1P', 8, {availableW: 2500}),
    NOW,
  );
  assert.equal(r.applicable, true);
  assert.equal(r.quality, 'GOOD');
  assert.equal(r.mode, '1P');
});

test('deadline path is explicitly bypassed and not reinterpreted by opportunity control', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(6000, {deadlineForceActive: true}),
    previous('3P', 8, {availableW: 6000}),
    NOW,
  );
  assert.equal(r.applicable, false);
  assert.equal(r.quality, 'BYPASS');
  assert.equal(r.reason, 'DEADLINE_PATH_OWNED_ELSEWHERE');
  assert.equal(r.phaseChanged, false);
  assert.equal(r.currentChanged, false);
});

test('stale P1 fails closed', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(6000, {p1Fresh: false}),
    previous('3P', 8, {availableW: 6000}),
    NOW,
  );
  assert.equal(r.quality, 'BLOCKED');
  assert.equal(r.mode, 'OFF');
  assert.equal(r.requestedA, 0);
  assert.equal(r.reason, 'P1_STALE');
});

test('candidate remains pure and performs no writes', () => {
  const r = evaluateEvPhaseCurrentCandidate(
    inputForAvailable(2500),
    previous('1P', 8, {availableW: 2500}),
    NOW,
  );
  assert.equal(r.shadow, true);
  assert.equal(r.deviceWrites, false);
  assert.equal(r.logicWrites, false);
});

test('wattsPerAmp is phase aware', () => {
  assert.equal(wattsPerAmp('1P'), 230);
  assert.equal(wattsPerAmp('3P'), 690);
  assert.equal(wattsPerAmp('OFF'), 0);
});

test('appendAvailableSample keeps bounded rolling state', () => {
  let s = [];
  for (let i = 0; i < 300; i += 1) {
    s = appendAvailableSample(s, NOW + i * 1000, 2000 + i);
  }
  assert.ok(s.length <= CONFIG.maxRollingSamples);
});
