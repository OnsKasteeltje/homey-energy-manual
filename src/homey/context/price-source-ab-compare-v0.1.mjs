#!/usr/bin/env node

/**
 * EnergyZero ↔ PBTH A/B comparator v0.1
 *
 * Status: GITHUB-ONLY / NO HOMEY CHANGE / SHADOW TOOLING
 *
 * Inputs:
 *   1) EnergyZero capture from energyzero-live-capture-v0.1.mjs
 *   2) PBTH shadow result from docs/snippets/pbth-api-shadow-v0.1.js
 *
 * PBTH importPrice is a configured consumer price. Its exact semantic mapping to
 * EnergyZero streams is therefore NOT assumed. This tool compares PBTH against
 * all EnergyZero streams by exact timestamp and reports the closest numerical
 * relationship for diagnosis only.
 *
 * Usage:
 *   node price-source-ab-compare-v0.1.mjs energyzero.json pbth-shadow.json
 */

import fs from 'node:fs/promises';

const STREAMS = [
  ['base', 'MARKET_EX_VAT'],
  ['base_with_vat', 'MARKET_WITH_VAT'],
  ['all_in', 'ALL_IN_EX_VAT'],
  ['all_in_with_vat', 'ALL_IN_WITH_VAT'],
];

function numberValue(v, label) {
  const n = typeof v === 'number' ? v : Number(v);
  if (!Number.isFinite(n)) throw new Error(`${label} is not numeric`);
  return n;
}

function iso(v, label) {
  const ms = Date.parse(v);
  if (!Number.isFinite(ms)) throw new Error(`${label} is not a valid timestamp`);
  return new Date(ms).toISOString();
}

function parseEnergyZero(capture, stream) {
  const payload = capture?.payload;
  if (!payload || !Array.isArray(payload[stream])) throw new Error(`EnergyZero payload.${stream} missing`);
  return payload[stream].map((r, i) => ({
    time: iso(r.start, `${stream}[${i}].start`),
    price: numberValue(r?.price?.value, `${stream}[${i}].price.value`),
  }));
}

function parsePbth(raw) {
  let result = raw;
  // Allow pasted HomeyScript return wrapped as {result: ...} or direct result.
  if (result?.result && typeof result.result === 'object') result = result.result;
  if (result?.status !== 'OK') throw new Error(`PBTH shadow status must be OK; got ${result?.status ?? 'missing'}`);
  if (!Array.isArray(result.slots) || result.slots.length === 0) throw new Error('PBTH shadow contains no slots');
  return {
    meta: result,
    slots: result.slots.map((s, i) => ({
      time: iso(s.time, `PBTH slots[${i}].time`),
      importPrice: numberValue(s.importPrice, `PBTH slots[${i}].importPrice`),
      exportPrice: s.exportPrice == null ? null : numberValue(s.exportPrice, `PBTH slots[${i}].exportPrice`),
      isForecast: Boolean(s.isForecast),
    })),
  };
}

function stats(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const abs = values.map(Math.abs);
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const meanAbs = abs.reduce((a, b) => a + b, 0) / abs.length;
  const rms = Math.sqrt(values.reduce((a, b) => a + b * b, 0) / values.length);
  const variance = values.reduce((a, b) => a + (b - mean) ** 2, 0) / values.length;
  return {
    count: values.length,
    mean,
    meanAbs,
    rms,
    stddev: Math.sqrt(variance),
    min: sorted[0],
    max: sorted.at(-1),
  };
}

function compareStream(ezRows, pbthSlots) {
  const ez = new Map(ezRows.map(r => [r.time, r.price]));
  const rows = [];
  for (const p of pbthSlots) {
    if (!ez.has(p.time)) continue;
    const e = ez.get(p.time);
    rows.push({
      time: p.time,
      pbthImport: p.importPrice,
      energyZero: e,
      deltaPbthMinusEz: p.importPrice - e,
      isForecast: p.isForecast,
    });
  }
  const all = stats(rows.map(r => r.deltaPbthMinusEz));
  const confirmed = stats(rows.filter(r => !r.isForecast).map(r => r.deltaPbthMinusEz));
  const forecast = stats(rows.filter(r => r.isForecast).map(r => r.deltaPbthMinusEz));
  return { rows, all, confirmed, forecast };
}

function fmt(n) {
  return n == null ? 'n/a' : Number(n).toFixed(6);
}

async function main() {
  const ezFile = process.argv[2];
  const pbthFile = process.argv[3];
  if (!ezFile || !pbthFile || ezFile === '--help' || ezFile === '-h') {
    console.log('Usage: node price-source-ab-compare-v0.1.mjs <energyzero-capture.json> <pbth-shadow.json>');
    process.exit(ezFile ? 0 : 2);
  }

  const ezCapture = JSON.parse(await fs.readFile(ezFile, 'utf8'));
  const pbthRaw = JSON.parse(await fs.readFile(pbthFile, 'utf8'));
  const pbth = parsePbth(pbthRaw);

  console.log(`EnergyZero capture: ${ezFile}`);
  console.log(`PBTH capture: ${pbthFile}`);
  console.log(`PBTH generatedAt: ${pbth.meta.generatedAt ?? 'unknown'}`);
  console.log(`PBTH slots: ${pbth.slots.length} (confirmed=${pbth.slots.filter(s => !s.isForecast).length}, forecast=${pbth.slots.filter(s => s.isForecast).length})`);
  console.log(`PBTH first/last: ${pbth.slots[0].time} -> ${pbth.slots.at(-1).time}`);

  const results = [];
  for (const [stream, basis] of STREAMS) {
    const cmp = compareStream(parseEnergyZero(ezCapture, stream), pbth.slots);
    results.push({ stream, basis, ...cmp });
    console.log('');
    console.log(`${stream} (${basis})`);
    console.log(`overlap: ${cmp.rows.length}/${pbth.slots.length}`);
    if (cmp.all) {
      console.log(`delta PBTH-EZ mean/meanAbs/stddev: ${fmt(cmp.all.mean)} / ${fmt(cmp.all.meanAbs)} / ${fmt(cmp.all.stddev)} EUR/kWh`);
      console.log(`delta min/max: ${fmt(cmp.all.min)} / ${fmt(cmp.all.max)} EUR/kWh`);
    }
    if (cmp.confirmed) console.log(`confirmed mean/stddev: ${fmt(cmp.confirmed.mean)} / ${fmt(cmp.confirmed.stddev)} (${cmp.confirmed.count} slots)`);
    if (cmp.forecast) console.log(`forecast mean/stddev: ${fmt(cmp.forecast.mean)} / ${fmt(cmp.forecast.stddev)} (${cmp.forecast.count} slots)`);
  }

  const candidates = results.filter(r => r.all).sort((a, b) => a.all.stddev - b.all.stddev || a.all.meanAbs - b.all.meanAbs);
  console.log('');
  if (!candidates.length) {
    console.log('RESULT: FAIL — no timestamp overlap between PBTH and EnergyZero.');
    process.exitCode = 1;
    return;
  }

  const best = candidates[0];
  console.log(`Closest-shape stream: ${best.stream} (${best.basis})`);
  console.log(`Reason: lowest delta stddev = ${fmt(best.all.stddev)} EUR/kWh; mean offset = ${fmt(best.all.mean)} EUR/kWh.`);
  console.log('Interpretation: diagnostic only. Do not infer semantic equivalence or enable failover from this result alone.');
}

main().catch(err => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
