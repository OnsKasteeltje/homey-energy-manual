import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const adapter = fs.readFileSync(
  'src/homey/adapters/ev-power/ev-power-v0.1.9.live-homey.js',
  'utf8'
);

const gate = fs.readFileSync(
  'src/homey/validation/ev-power-adapter-gate-v0.2.10.live-homey.js',
  'utf8'
);

const actuator = fs.readFileSync(
  'src/homey/actuators/ev-power/ev-power-v0.2.14.live-homey.js',
  'utf8'
);

test('Adapter keeps state freshness observability-only', () => {
  assert.match(adapter, /rawCoreRevisionIsObservabilityOnly:true/);
  assert.match(adapter, /intentFresh,stateFresh,chargerAvailable/);

  assert.doesNotMatch(
    adapter,
    /if\s*\(\s*!stateFresh\s*\)/
  );
});

test('Gate does not use stale state timestamp as independent veto', () => {
  assert.match(gate, /coreSafety:coreStateSafe/);

  assert.doesNotMatch(
    gate,
    /coreSafety:stateFresh&&coreStateSafe/
  );
});

test('Gate refresh is not suppressed by same-semantic early return', () => {
  assert.doesNotMatch(
    gate,
    /prev\?\.semantic===semantic\)return/
  );
});

test('Actuator requires fresh intent and Gate, not fresh Adapter timestamp', () => {
  assert.match(
    actuator,
    /normalControlFresh=intentFresh&&gateFresh/
  );

  assert.doesNotMatch(
    actuator,
    /normalControlFresh=intentFresh&&adapterFresh&&gateFresh/
  );
});

test('Post-session coherence does not require raw state timestamp freshness', () => {
  assert.match(
    actuator,
    /normalCoherent=liveVar\.value===true&&intentFresh&&gateFresh/
  );

  assert.doesNotMatch(
    actuator,
    /normalCoherent=.*stateFresh/
  );
});

test('single physical writer safety remains present', () => {
  assert.match(adapter, /physicalWriter:'DISABLED'/);

  assert.match(
    actuator,
    /live:'8d47e98d-e4bc-4f47-8c02-c2aca7f7a978'/
  );

  assert.match(
    actuator,
    /if\(liveVar\.value!==true\)/
  );
});
