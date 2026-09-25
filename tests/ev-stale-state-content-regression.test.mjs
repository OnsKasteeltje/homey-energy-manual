import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const adapter = fs.readFileSync(
  'src/homey/adapters/ev-power/ev-power-v0.1.10.control-pure.js',
  'utf8'
);

const gate = fs.readFileSync(
  'src/homey/validation/ev-power-adapter-gate-v0.2.11.control-contract.js',
  'utf8'
);

const actuator = fs.readFileSync(
  'src/homey/actuators/ev-power/ev-power-v0.2.15.control-authority.js',
  'utf8'
);

test('Adapter cannot veto control from stale chargeState content', () => {
  assert.doesNotMatch(adapter, /CHARGER_UNAVAILABLE/);
  assert.doesNotMatch(adapter, /chargerAvailable/);
  assert.doesNotMatch(adapter, /cs\.includes\(['"]offline/);
  assert.match(adapter, /chargeStateObservabilityOnly:true/);
});

test('Gate cannot veto control from stale chargeState content', () => {
  assert.doesNotMatch(gate, /coreStateSafe/);
  assert.doesNotMatch(gate, /coreSafety:/);
  assert.doesNotMatch(gate, /cs\.includes\(['"]offline/);
  assert.match(gate, /coreStateObservabilityOnly:true/);
});

test('Actuator does not fail closed solely from Core chargeState', () => {
  assert.doesNotMatch(actuator, /CORE_CHARGER_STATE_UNSAFE/);
  assert.doesNotMatch(actuator, /STALE_STATE_NO_DEADLINE_AUTHORITY/);
});

test('Actuator normal authority does not depend on chargeState', () => {
  const match = actuator.match(
    /const normalCoherent=([^;]+);/
  );

  assert.ok(match, 'normalCoherent definition missing');

  assert.doesNotMatch(match[1], /cs/);
  assert.doesNotMatch(match[1], /explicitUnsafe/);
  assert.doesNotMatch(match[1], /connectedState/);

  assert.match(match[1], /intentFresh/);
  assert.match(match[1], /gateFresh/);
  assert.match(match[1], /gatePass/);
  assert.match(match[1], /tokenOK/);
  assert.match(match[1], /adapterSafe/);
  assert.match(match[1], /numericOK/);
});

test('Deadline authority does not depend on stale chargeState', () => {
  const matches = [
    ...actuator.matchAll(/const deadlineAuthority=([^;]+);/g)
  ];

  assert.ok(matches.length >= 2, 'expected both actuator stages');

  for (const match of matches) {
    assert.doesNotMatch(match[1], /cs/);
    assert.doesNotMatch(match[1], /explicitUnsafe/);
    assert.doesNotMatch(match[1], /connectedState/);

    assert.match(match[1], /deadlineEligible/);
    assert.match(match[1], /gateFresh/);
    assert.match(match[1], /gatePass/);
    assert.match(match[1], /tokenOK/);
    assert.match(match[1], /adapterSafe/);
    assert.match(match[1], /numericOK/);
  }
});

test('Actuator remains sole guarded physical writer', () => {
  assert.match(actuator, /setCapabilityValue\('target_charger_current'/);
  assert.match(actuator, /if\(liveVar\.value!==true\)/);

  assert.match(
    actuator,
    /if\(!gateFresh\)return await failClosed/
  );

  assert.match(
    actuator,
    /if\(!gatePass\)return await failClosed/
  );
});

test('Actuator version matches canonical candidate', () => {
  const versions = [
    ...actuator.matchAll(
      /const VERSION='([^']+)'/g
    )
  ].map(x => x[1]);

  assert.ok(versions.length >= 2);

  for (const version of versions) {
    assert.equal(version, 'EM2_EV_ACTUATOR_V0.2.15');
  }
});
