
import fs from 'node:fs/promises';
import https from 'node:https';
import { normalizeEnergyZeroRest } from './price-source-normalizer-v0.1.mjs';

const API = 'https://public.api.energyzero.nl/public/v1/prices';
const OUTPUT = '/home/jeroen/ems/data/price-forecast.json';
const TIME_ZONE = 'Europe/Amsterdam';

function localDate(offsetDays = 0) {
  const now = new Date(Date.now() + offsetDays * 86400000);
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).formatToParts(now);

  const map = Object.fromEntries(
    parts.filter(p => p.type !== 'literal').map(p => [p.type, p.value])
  );

  return `${map.year}-${map.month}-${map.day}`;
}

function apiDate(dateString) {
  const [y, m, d] = dateString.split('-');
  return `${d}-${m}-${y}`;
}

function getJson(url, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        accept: 'application/json',
        'user-agent': 'ems-pi-price-forecast/0.1'
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
          reject(new Error(`Invalid EnergyZero JSON: ${err.message}`));
        }
      });
    });

    req.setTimeout(timeoutMs, () => req.destroy(new Error('EnergyZero request timeout')));
    req.on('error', reject);
  });
}

async function fetchDate(date) {
  const params = new URLSearchParams({
    energyType: 'ENERGY_TYPE_ELECTRICITY',
    date: apiDate(date),
    interval: 'INTERVAL_QUARTER'
  });

  const retrievedAt = new Date().toISOString();
  const payload = await getJson(`${API}?${params.toString()}`);

  return normalizeEnergyZeroRest(payload, {
    retrievedAt,
    localDate: date,
    timeZone: TIME_ZONE,
    stream: 'base',
    priceBasis: 'MARKET_EX_VAT'
  });
}

async function main() {
  const today = localDate(0);
  const tomorrow = localDate(1);

  const todayData = await fetchDate(today);
  const tomorrowData = await fetchDate(tomorrow);

  const now = Date.now();

  const slots = [...todayData.slots, ...tomorrowData.slots]
    .filter(slot => Date.parse(slot.end) > now)
    .sort((a, b) => Date.parse(a.start) - Date.parse(b.start))
    .slice(0, 96);

  if (slots.length === 0) {
    throw new Error('No usable EnergyZero slots available');
  }

  const output = {
    schema: 'EMS_PI_PRICE_FORECAST_V0.1',
    generated_at_utc: new Date().toISOString(),
    source: 'ENERGYZERO_PUBLIC_REST',
    price_basis: 'MARKET_EX_VAT',
    currency: 'EUR',
    resolution_minutes: 15,
    slot_count: slots.length,
    horizon_end_utc: slots.at(-1).end,
    slots
  };

  await fs.writeFile(OUTPUT, JSON.stringify(output, null, 2) + '\n', 'utf8');

  console.log(`Wrote ${OUTPUT}`);
  console.log(`Slots: ${slots.length}`);
  console.log(`First: ${slots[0].start}`);
  console.log(`Last : ${slots.at(-1).start}`);
}

main().catch(err => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
