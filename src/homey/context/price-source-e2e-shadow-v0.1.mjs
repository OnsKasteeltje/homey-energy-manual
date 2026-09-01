// Price Source E2E Shadow v0.1
// GITHUB-ONLY / READ-ONLY / NO HOMEY WRITES / NO PRODUCTION CUTOVER
//
// Purpose: combine already captured PBTH Inter-App data with a live EnergyZero
// public REST fetch, normalize both sources, and run the deterministic shadow selector.
// This Node/Pi-compatible runner intentionally does not call Homey itself.

import https from 'node:https';
import fs from 'node:fs/promises';
import { normalizeEnergyZeroRest, normalizePbthInterApp } from './price-source-normalizer-v0.1.mjs';
import { selectPriceSourceShadow } from './price-source-selector-v0.1.mjs';

const ENERGYZERO_HOST = 'public.api.energyzero.nl';
const ENERGYZERO_PATH = '/public/v1/prices';
const TIME_ZONE = 'Europe/Amsterdam';

function getJson(host, path) {
  return new Promise((resolve, reject) => {
    https.get({ host, path, headers: { accept: 'application/json' } }, (res) => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => {
        if ((res.statusCode ?? 500) < 200 || (res.statusCode ?? 500) >= 300) {
          reject(new Error(`HTTP ${res.statusCode}: ${body.slice(0, 300)}`));
          return;
        }
        try { resolve(JSON.parse(body)); }
        catch (err) { reject(new Error(`Invalid JSON: ${err.message}`)); }
      });
    }).on('error', reject);
  });
}

function localDateInZone(date = new Date(), timeZone = TIME_ZONE) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date);
  const map = Object.fromEntries(parts.filter((p) => p.type !== 'literal').map((p) => [p.type, p.value]));
  return `${map.year}-${map.month}-${map.day}`;
}

function toEnergyZeroDate(localDate) {
  const [y, m, d] = localDate.split('-');
  return `${d}-${m}-${y}`;
}

function unwrapPbth(input) {
  if (input?.prices) return input;
  if (input?.data?.prices) return input.data;
  if (input?.raw?.prices) return input.raw;
  throw new Error('PBTH input must contain the raw Inter-App /dap-prices response with a prices array');
}

async function main() {
  const pbthFile = process.argv[2];
  const localDate = process.argv[3] || localDateInZone();
  const requiredHorizonEnd = process.argv[4] || null;

  if (!pbthFile) {
    console.error('Usage: node price-source-e2e-shadow-v0.1.mjs <pbth-raw.json> [YYYY-MM-DD] [required-horizon-ISO]');
    console.error('PBTH file must be a raw /dap-prices Inter-App response, not the compact HomeyScript summary.');
    process.exitCode = 2;
    return;
  }

  const pbthRaw = unwrapPbth(JSON.parse(await fs.readFile(pbthFile, 'utf8')));
  const retrievedAt = new Date().toISOString();
  const query = new URLSearchParams({
    energyType: 'ENERGY_TYPE_ELECTRICITY',
    date: toEnergyZeroDate(localDate),
    interval: 'INTERVAL_QUARTER',
  });
  const ezRaw = await getJson(ENERGYZERO_HOST, `${ENERGYZERO_PATH}?${query}`);

  const energyZero = normalizeEnergyZeroRest(ezRaw, {
    retrievedAt,
    localDate,
    timeZone: TIME_ZONE,
    stream: 'base',
    priceBasis: 'MARKET_EX_VAT',
  });

  // Live A/B validation on 2026-09-01 established PBTH importPrice == EnergyZero
  // base MARKET_EX_VAT for 109/109 overlapping NL DAP15 slots. We therefore make
  // that proven semantic basis explicit only in this SHADOW runner.
  const pbth = normalizePbthInterApp(pbthRaw, { retrievedAt });
  pbth.priceBasis = 'MARKET_EX_VAT';
  pbth.slots = pbth.slots.map((slot) => ({
    ...slot,
    marketPriceEurPerKwh: slot.importPriceEurPerKwh,
  }));

  const result = selectPriceSourceShadow([energyZero, pbth], {
    now: retrievedAt,
    requiredHorizonEnd,
    maxAgeMinutes: 30,
  });

  const compact = {
    schema: 'EM2_PRICE_SOURCE_E2E_SHADOW_V0.1',
    status: result.status,
    mode: 'SHADOW_READ_ONLY',
    generatedAt: retrievedAt,
    requestedLocalDate: localDate,
    requiredHorizonEnd,
    selectedSource: result.selectedSource,
    selectedHorizonEnd: result.selectedHorizonEnd,
    productionSwitchAllowed: false,
    evaluations: result.evaluations,
    note: 'PBTH MARKET_EX_VAT mapping is shadow-only and based on 2026-09-01 live A/B 109/109 exact match.',
  };

  console.log(JSON.stringify(compact, null, 2));
}

main().catch((err) => {
  console.error(JSON.stringify({
    schema: 'EM2_PRICE_SOURCE_E2E_SHADOW_V0.1',
    status: 'ERROR',
    mode: 'SHADOW_READ_ONLY',
    error: String(err?.message || err),
    productionSwitchAllowed: false,
  }, null, 2));
  process.exitCode = 1;
});
