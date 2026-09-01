import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { normalizeEnergyZeroRest } from '../../homey/context/price-source-normalizer-v0.1.mjs';
import { selectPriceSourceShadow } from '../../homey/context/price-source-selector-v0.1.mjs';
import { logger } from './lib/logger.mjs';
import { startHealthServer } from './lib/health.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CONFIG_PATH = process.env.HEMS_CONFIG || path.join(__dirname, 'config.json');
const RUN_ONCE = process.env.HEMS_RUN_ONCE === '1';

let state = {
  schema: 'HEMS_PI_RUNTIME_STATE_V0.1',
  mode: 'SHADOW_READ_ONLY',
  runtimeStatus: 'STARTING',
  startedAt: new Date().toISOString(),
  lastRunAt: null,
  lastSuccessAt: null,
  lastError: null,
  price: null,
  planner: { enabled: false, status: 'NOT_WIRED' },
  writes: { logic: false, devices: false, physicalActuators: false },
};

function localDateInZone(date = new Date(), timeZone = 'Europe/Amsterdam') {
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

async function readConfig() {
  try {
    return JSON.parse(await fs.readFile(CONFIG_PATH, 'utf8'));
  } catch (err) {
    if (err?.code === 'ENOENT') {
      const example = path.join(__dirname, 'config.example.json');
      logger.warn('CONFIG_FALLBACK', { requested: CONFIG_PATH, using: example });
      return JSON.parse(await fs.readFile(example, 'utf8'));
    }
    throw err;
  }
}

async function fetchEnergyZero(config, localDate) {
  const url = new URL(config.priceSources.energyZero.baseUrl);
  url.searchParams.set('energyType', 'ENERGY_TYPE_ELECTRICITY');
  url.searchParams.set('date', toEnergyZeroDate(localDate));
  url.searchParams.set('interval', 'INTERVAL_QUARTER');

  const response = await fetch(url, { headers: { accept: 'application/json' } });
  if (!response.ok) throw new Error(`EnergyZero HTTP ${response.status}`);
  return response.json();
}

async function runCycle(config) {
  const generatedAt = new Date().toISOString();
  state = { ...state, lastRunAt: generatedAt, lastError: null };

  if (config.mode !== 'SHADOW_READ_ONLY') throw new Error(`Unsupported mode ${config.mode}`);
  if (config.writes?.logic || config.writes?.devices || config.writes?.physicalActuators) {
    throw new Error('Safety guard: all writes must remain false in Pi runtime v0.1');
  }

  const localDate = localDateInZone(new Date(), config.timeZone);
  const requiredHorizonEnd = new Date(Date.now() + Number(config.requiredHorizonHours || 24) * 3600_000).toISOString();
  const sources = [];

  if (config.priceSources?.energyZero?.enabled) {
    const raw = await fetchEnergyZero(config, localDate);
    // Keep the complete stream returned for the requested date instead of filtering
    // back to one local calendar day: EnergyZero currently returns a wider horizon,
    // and the selector must validate that actual forward horizon.
    const source = normalizeEnergyZeroRest(raw, {
      retrievedAt: generatedAt,
      timeZone: config.timeZone,
      stream: 'base',
      priceBasis: 'MARKET_EX_VAT',
    });
    sources.push(source);
  }

  // PBTH deliberately not fetched by this first Pi runtime. A read-only Pi bridge/input
  // contract must be designed and validated before it can become a second live source.
  const selection = selectPriceSourceShadow(sources, {
    now: generatedAt,
    requiredHorizonEnd,
    maxAgeMinutes: 30,
  });

  state = {
    ...state,
    runtimeStatus: selection.status === 'OK' ? 'OK' : 'DEGRADED',
    lastSuccessAt: generatedAt,
    price: {
      generatedAt,
      requestedLocalDate: localDate,
      requiredHorizonEnd,
      selection,
    },
  };

  logger.info('PRICE_SHADOW_CYCLE', {
    status: selection.status,
    selectedSource: selection.selectedSource,
    selectedHorizonEnd: selection.selectedHorizonEnd,
    productionSwitchAllowed: false,
  });
}

async function main() {
  const config = await readConfig();
  state = {
    ...state,
    mode: config.mode,
    planner: { enabled: Boolean(config.planner?.enabled), status: 'NOT_WIRED' },
    writes: config.writes,
  };

  const server = startHealthServer({
    host: config.health?.host || '127.0.0.1',
    port: Number(config.health?.port || 8787),
    getState: () => state,
  });
  logger.info('RUNTIME_STARTED', {
    mode: config.mode,
    health: `${config.health?.host || '127.0.0.1'}:${Number(config.health?.port || 8787)}`,
    runOnce: RUN_ONCE,
  });

  const execute = async () => {
    try {
      await runCycle(config);
    } catch (err) {
      state = {
        ...state,
        runtimeStatus: 'ERROR',
        lastError: { at: new Date().toISOString(), message: String(err?.message || err) },
      };
      logger.error('PRICE_SHADOW_CYCLE_FAILED', { error: state.lastError.message });
    }
  };

  await execute();
  if (RUN_ONCE) {
    server.close();
    if (state.runtimeStatus === 'ERROR') process.exitCode = 1;
    return;
  }

  const intervalMs = Math.max(60, Number(config.pollIntervalSeconds || 900)) * 1000;
  const timer = setInterval(execute, intervalMs);

  const shutdown = (signal) => {
    logger.info('RUNTIME_STOPPING', { signal });
    clearInterval(timer);
    server.close(() => process.exit(0));
  };
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}

main().catch((err) => {
  logger.error('RUNTIME_FATAL', { error: String(err?.message || err) });
  process.exitCode = 1;
});
