import test from "node:test";
import assert from "node:assert/strict";
import { mapEvPowerIntent, EV_POWER_ADAPTER_REVISION } from "../docs/javascripts/ev-power-adapter-shadow-v0.1.js";

const NOW = Date.parse("2026-08-26T18:00:00.000Z");

function valid(overrides = {}) {
  return {
    targetW: 0,
    intentTimestampMs: NOW - 1_000,
    chargerAvailable: true,
    chargerState: "plugged_in",
    chargerStateTimestampMs: NOW - 1_000,
    maxCurrentA: 16,
    nowMs: NOW,
    sourceRevision: 42,
    ...overrides,
  };
}

test("zero intent maps to zero without a write", () => {
  const out = mapEvPowerIntent(valid({ targetW: 0 }));
  assert.equal(out.requestedA, 0);
  assert.equal(out.executableW, 0);
  assert.equal(out.reason, "ZERO_INTENT");
  assert.equal(out.deviceWrites, false);
  assert.equal(out.commandedA, null);
  assert.equal(out.schema, EV_POWER_ADAPTER_REVISION);
});

test("just below 3x6A minimum fails closed", () => {
  const out = mapEvPowerIntent(valid({ targetW: 4139 }));
  assert.equal(out.requestedA, 0);
  assert.equal(out.executableW, 0);
  assert.equal(out.reason, "BELOW_MINIMUM_EXECUTABLE_POWER");
});

test("exact 3x6A minimum is executable", () => {
  const out = mapEvPowerIntent(valid({ targetW: 4140 }));
  assert.equal(out.requestedA, 6);
  assert.equal(out.executableW, 4140);
  assert.equal(out.deltaW, 0);
});

test("6200W quantizes down to 3x8A and never exceeds intent", () => {
  const out = mapEvPowerIntent(valid({ targetW: 6200 }));
  assert.equal(out.requestedA, 8);
  assert.equal(out.executableW, 5520);
  assert.equal(out.deltaW, -680);
  assert.equal(out.reason, "QUANTIZED_DOWN");
});

test("6210W maps exactly to 3x9A", () => {
  const out = mapEvPowerIntent(valid({ targetW: 6210 }));
  assert.equal(out.requestedA, 9);
  assert.equal(out.executableW, 6210);
  assert.equal(out.deltaW, 0);
});

test("target above configured maximum is clamped", () => {
  const out = mapEvPowerIntent(valid({ targetW: 30_000, maxCurrentA: 16 }));
  assert.equal(out.requestedA, 16);
  assert.equal(out.executableW, 11_040);
  assert.equal(out.reason, "CLAMPED_TO_MAX_CURRENT");
});

test("stale intent fails closed", () => {
  const out = mapEvPowerIntent(valid({ targetW: 6210, intentTimestampMs: NOW - 120_001 }));
  assert.equal(out.requestedA, 0);
  assert.equal(out.reason, "STALE_INTENT");
  assert.equal(out.inputFresh, false);
});

test("stale charger state fails closed", () => {
  const out = mapEvPowerIntent(valid({ targetW: 6210, chargerStateTimestampMs: NOW - 120_001 }));
  assert.equal(out.requestedA, 0);
  assert.equal(out.reason, "STALE_CHARGER_STATE");
});

test("unavailable charger fails closed", () => {
  const out = mapEvPowerIntent(valid({ targetW: 6210, chargerAvailable: false }));
  assert.equal(out.requestedA, 0);
  assert.equal(out.reason, "CHARGER_UNAVAILABLE");
});

test("invalid intent fails closed", () => {
  const out = mapEvPowerIntent(valid({ targetW: Number.NaN }));
  assert.equal(out.requestedA, 0);
  assert.equal(out.reason, "INVALID_INTENT");
});

test("configured max below minimum fails closed", () => {
  const out = mapEvPowerIntent(valid({ targetW: 6210, maxCurrentA: 5 }));
  assert.equal(out.requestedA, 0);
  assert.equal(out.reason, "MAX_CURRENT_BELOW_MINIMUM");
});

test("normal mapping invariant: executable power never exceeds upstream intent", () => {
  for (let targetW = 0; targetW <= 20_000; targetW += 1) {
    const out = mapEvPowerIntent(valid({ targetW }));
    assert.ok(out.executableW <= targetW, `${targetW}: ${out.executableW} > ${targetW}`);
    assert.ok(out.requestedA === 0 || out.requestedA >= 6);
    assert.equal(out.deviceWrites, false);
    assert.equal(out.commandedA, null);
  }
});
