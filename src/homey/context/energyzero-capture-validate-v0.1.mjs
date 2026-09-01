#!/usr/bin/env node

/**
 * EnergyZero capture validator v0.1
 *
 * Status: GITHUB-ONLY / NO HOMEY CHANGE / SHADOW TOOLING
 *
 * Reads a capture created by energyzero-live-capture-v0.1.mjs and validates
 * one or more Europe/Amsterdam local calendar days through the canonical
 * price-source normalizer.
 *
 * Usage:
 *   node energyzero-capture-validate-v0.1.mjs energyzero-2026-09-01.json
 *   node energyzero-capture-validate-v0.1.mjs energyzero-2026-09-01.json 2026-09-01 2026-09-02
 */

import fs from 'node:fs/promises';
import { normalizeEnergyZeroRest } from './price-source-normalizer-v0.1.mjs';

function printUsage() {
  console.log('Usage: node energyzero-capture-validate-v0.1.mjs <capture.json> [YYYY-MM-DD ...]');
  console.log('Example: node energyzero-capture-validate-v0.1.mjs energyzero-2026-09-01.json 2026-09-01 2026-09-02');
}

function nextLocalDate(dateString) {
  const [y, m, d] = dateString.split('-').map(Number);
  const x = new Date(Date.UTC(y, m - 1, d + 1, 12, 0, 0));
  return x.toISOString().slice(0, 10);
}

function summarize(normalized) {
  const prices = normalized.slots.map(slot => slot.marketPriceEurPerKwh);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const avg = prices.reduce((sum, value) => sum + value, 0) / prices.length;
  return {
    source: normalized.source,
    date: normalized.sourceMeta.localDate,
    slots: normalized.slots.length,
    priceBasis: normalized.priceBasis,
    first: normalized.slots[0],
    last: normalized.slots.at(-1),
    min,
    max,
    avg,
    complete: normalized.health.complete,
    horizonEnd: normalized.health.horizonEnd,
  };
}

async function main() {
  const file = process.argv[2];
  const dates = process.argv.slice(3);

  if (!file || file === '--help' || file === '-h') {
    printUsage();
    if (!file) process.exit(2);
    return;
  }

  const capture = JSON.parse(await fs.readFile(file, 'utf8'));
  const payload = capture?.payload;
  if (!payload || typeof payload !== 'object') {
    throw new Error('Capture does not contain payload');
  }

  const requested = dates.length
    ? dates
    : [capture.requestedLocalDate, nextLocalDate(capture.requestedLocalDate)].filter(Boolean);

  console.log(`Capture: ${file}`);
  console.log(`Retrieved: ${capture.retrievedAt ?? 'unknown'}`);
  console.log(`Raw streams: ${JSON.stringify({
    base: Array.isArray(payload.base) ? payload.base.length : null,
    base_with_vat: Array.isArray(payload.base_with_vat) ? payload.base_with_vat.length : null,
    all_in: Array.isArray(payload.all_in) ? payload.all_in.length : null,
    all_in_with_vat: Array.isArray(payload.all_in_with_vat) ? payload.all_in_with_vat.length : null,
  })}`);

  for (const localDate of requested) {
    try {
      const normalized = normalizeEnergyZeroRest(payload, {
        localDate,
        retrievedAt: capture.retrievedAt ?? new Date().toISOString(),
      });
      const s = summarize(normalized);
      console.log('');
      console.log(`${s.date}: PASS`);
      console.log(`slots: ${s.slots}`);
      console.log(`priceBasis: ${s.priceBasis}`);
      console.log(`first: ${s.first.start} -> ${s.first.end} = ${s.first.marketPriceEurPerKwh} EUR/kWh`);
      console.log(`last : ${s.last.start} -> ${s.last.end} = ${s.last.marketPriceEurPerKwh} EUR/kWh`);
      console.log(`min/avg/max: ${s.min.toFixed(6)} / ${s.avg.toFixed(6)} / ${s.max.toFixed(6)} EUR/kWh`);
      console.log(`complete: ${s.complete}`);
      console.log(`horizonEnd: ${s.horizonEnd}`);
    } catch (err) {
      console.log('');
      console.log(`${localDate}: FAIL`);
      console.log(`${err?.code ? `${err.code}: ` : ''}${err?.message ?? String(err)}`);
    }
  }
}

main().catch(err => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
