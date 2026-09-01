#!/usr/bin/env node

/**
 * EnergyZero live capture helper v0.1
 *
 * Status: GITHUB-ONLY / NO HOMEY CHANGE / SHADOW TOOLING
 *
 * Fetches Dutch electricity quarter-hour prices from the current EnergyZero
 * public REST API and writes the raw JSON payload to stdout or an optional file.
 *
 * Usage:
 *   node energyzero-live-capture-v0.1.mjs 2026-09-01
 *   node energyzero-live-capture-v0.1.mjs 2026-09-01 ./energyzero-2026-09-01.json
 *   node energyzero-live-capture-v0.1.mjs --help
 *
 * The requested date is interpreted as Europe/Amsterdam local calendar date.
 * Compatible with Node.js 17+; does not depend on global fetch().
 *
 * Source contract verified against python-energyzero REST client:
 *   GET https://public.api.energyzero.nl/public/v1/prices
 *   energyType=ENERGY_TYPE_ELECTRICITY
 *   date=DD-MM-YYYY
 *   interval=INTERVAL_QUARTER
 *
 * For EMS source comparison we use payload.base, which is the MARKET stream
 * (EUR/kWh, excluding VAT/additional supplier costs). Contract economics remain
 * the responsibility of the Contract Price Adapter.
 */

import fs from 'node:fs/promises';
import https from 'node:https';

const API = 'https://public.api.energyzero.nl/public/v1/prices';
const ENERGY_TYPE = 'ENERGY_TYPE_ELECTRICITY';
const INTERVAL = 'INTERVAL_QUARTER';
const MARKET_STREAM = 'base';

function apiDate(dateString) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
    throw new Error(`Expected date YYYY-MM-DD, got: ${dateString}`);
  }
  const [y, m, d] = dateString.split('-');
  return `${d}-${m}-${y}`;
}

function getJson(url, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        accept: 'application/json',
        'user-agent': 'homey-energy-manual-shadow/0.1'
      }
    }, res => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', chunk => { body += chunk; });
      res.on('end', () => {
        const status = res.statusCode ?? 0;
        if (status < 200 || status >= 300) {
          reject(new Error(`EnergyZero HTTP ${status}: ${body}`));
          return;
        }
        try {
          resolve(JSON.parse(body));
        } catch (err) {
          reject(new Error(`EnergyZero returned invalid JSON: ${err.message}`));
        }
      });
    });

    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error(`EnergyZero request timed out after ${timeoutMs} ms`));
    });
    req.on('error', reject);
  });
}

function printUsage() {
  console.log('Usage: node energyzero-live-capture-v0.1.mjs YYYY-MM-DD [output.json]');
  console.log('Example: node energyzero-live-capture-v0.1.mjs 2026-09-01 energyzero-2026-09-01.json');
}

function priceValue(slot) {
  const value = slot?.price?.value;
  return typeof value === 'number' ? value : Number(value);
}

async function main() {
  const date = process.argv[2];
  const outputFile = process.argv[3] ?? null;

  if (date === '--help' || date === '-h') {
    printUsage();
    return;
  }

  if (!date) {
    printUsage();
    process.exit(2);
  }

  const params = new URLSearchParams({
    energyType: ENERGY_TYPE,
    date: apiDate(date),
    interval: INTERVAL
  });

  const url = `${API}?${params.toString()}`;
  const retrievedAt = new Date().toISOString();
  const payload = await getJson(url);

  const prices = Array.isArray(payload?.[MARKET_STREAM]) ? payload[MARKET_STREAM] : [];
  if (prices.length === 0) {
    throw new Error(`EnergyZero returned no ${MARKET_STREAM} quarter-hour prices for ${date}`);
  }

  const invalid = prices.find(slot =>
    !slot?.start || !slot?.end || !Number.isFinite(priceValue(slot))
  );
  if (invalid) {
    throw new Error('EnergyZero MARKET stream contains an invalid price slot');
  }

  const capture = {
    captureVersion: 'energyzero-live-v0.1',
    requestedLocalDate: date,
    retrievedAt,
    request: {
      url,
      energyType: ENERGY_TYPE,
      interval: INTERVAL,
      timezone: 'Europe/Amsterdam'
    },
    selectedStream: {
      key: MARKET_STREAM,
      priceType: 'MARKET',
      priceBasis: 'MARKET_EX_VAT',
      unit: 'EUR/kWh'
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

  console.error(`EnergyZero MARKET slots: ${prices.length}`);
  console.error(`First: ${prices[0].start} -> ${prices[0].end} = ${priceValue(prices[0])} EUR/kWh`);
  console.error(`Last : ${prices.at(-1).start} -> ${prices.at(-1).end} = ${priceValue(prices.at(-1))} EUR/kWh`);

  const streamNames = ['base', 'base_with_vat', 'all_in', 'all_in_with_vat'];
  const counts = Object.fromEntries(streamNames.map(key => [key, Array.isArray(payload?.[key]) ? payload[key].length : 0]));
  console.error(`Streams: ${JSON.stringify(counts)}`);
}

main().catch(err => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
