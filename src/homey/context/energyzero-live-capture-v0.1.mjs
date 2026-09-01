#!/usr/bin/env node

/**
 * EnergyZero live capture helper v0.1
 *
 * Status: GITHUB-ONLY / NO HOMEY CHANGE / SHADOW TOOLING
 *
 * Fetches Dutch electricity quarter-hour prices from the EnergyZero public API
 * and writes the raw JSON payload to stdout or an optional file.
 *
 * Usage:
 *   node energyzero-live-capture-v0.1.mjs 2026-09-01
 *   node energyzero-live-capture-v0.1.mjs 2026-09-01 ./energyzero-2026-09-01.json
 *
 * The requested date is interpreted as Europe/Amsterdam local calendar date.
 */

import fs from 'node:fs/promises';

const API = 'https://api.energyzero.nl/v1/energyprices';

function amsterdamUtcRange(dateString) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
    throw new Error(`Expected date YYYY-MM-DD, got: ${dateString}`);
  }

  // Determine UTC offset for Europe/Amsterdam at local noon, then construct
  // local midnight boundaries robustly for CET/CEST and DST transition days.
  const [y, m, d] = dateString.split('-').map(Number);

  const localNoonAsUtc = new Date(Date.UTC(y, m - 1, d, 12, 0, 0));
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Amsterdam',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hourCycle: 'h23'
  });

  function offsetMs(at) {
    const parts = Object.fromEntries(fmt.formatToParts(at)
      .filter(p => p.type !== 'literal')
      .map(p => [p.type, p.value]));
    const representedAsUtc = Date.UTC(
      Number(parts.year), Number(parts.month) - 1, Number(parts.day),
      Number(parts.hour), Number(parts.minute), Number(parts.second)
    );
    return representedAsUtc - at.getTime();
  }

  function localMidnightUtc(yy, mm, dd) {
    let guess = new Date(Date.UTC(yy, mm - 1, dd, 0, 0, 0));
    // Two iterations handle offset differences around DST boundaries.
    for (let i = 0; i < 2; i++) {
      guess = new Date(Date.UTC(yy, mm - 1, dd, 0, 0, 0) - offsetMs(guess));
    }
    return guess;
  }

  const start = localMidnightUtc(y, m, d);
  const next = new Date(Date.UTC(y, m - 1, d + 1, 12, 0, 0));
  const nextParts = Object.fromEntries(fmt.formatToParts(next)
    .filter(p => p.type !== 'literal')
    .map(p => [p.type, p.value]));
  const endExclusive = localMidnightUtc(
    Number(nextParts.year), Number(nextParts.month), Number(nextParts.day)
  );

  return {
    fromDate: start.toISOString().replace('.000Z', '.000Z'),
    tillDate: new Date(endExclusive.getTime() - 1).toISOString()
  };
}

async function main() {
  const date = process.argv[2];
  const outputFile = process.argv[3] ?? null;
  if (!date) {
    console.error('Usage: node energyzero-live-capture-v0.1.mjs YYYY-MM-DD [output.json]');
    process.exit(2);
  }

  const { fromDate, tillDate } = amsterdamUtcRange(date);
  const params = new URLSearchParams({
    fromDate,
    tillDate,
    interval: '3',
    usageType: '1',
    inclBtw: 'false'
  });

  const url = `${API}?${params.toString()}`;
  const retrievedAt = new Date().toISOString();
  const response = await fetch(url, {
    headers: { 'accept': 'application/json', 'user-agent': 'homey-energy-manual-shadow/0.1' }
  });

  if (!response.ok) {
    throw new Error(`EnergyZero HTTP ${response.status}: ${await response.text()}`);
  }

  const payload = await response.json();
  const capture = {
    captureVersion: 'energyzero-live-v0.1',
    requestedLocalDate: date,
    retrievedAt,
    request: {
      url,
      interval: 3,
      usageType: 1,
      inclBtw: false,
      timezone: 'Europe/Amsterdam'
    },
    payload
  };

  const json = JSON.stringify(capture, null, 2) + '\n';
  if (outputFile) {
    await fs.writeFile(outputFile, json, 'utf8');
    console.error(`Wrote ${outputFile}`);
  } else {
    process.stdout.write(json);
  }

  const prices = Array.isArray(payload?.Prices) ? payload.Prices : [];
  console.error(`EnergyZero slots: ${prices.length}`);
  if (prices.length) {
    console.error(`First: ${prices[0].readingDate} = ${prices[0].price}`);
    console.error(`Last : ${prices.at(-1).readingDate} = ${prices.at(-1).price}`);
  }
}

main().catch(err => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
