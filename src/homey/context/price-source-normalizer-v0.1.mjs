const NL_ZONE = '10YNL----------L';
const FIFTEEN_MIN_MS = 15 * 60 * 1000;

export class PriceSourceError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'PriceSourceError';
    this.code = code;
  }
}

function assertFiniteNumber(value, code, label) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new PriceSourceError(code, `${label} must be a finite number`);
  }
  return value;
}

function toIso(value, code, label) {
  const ms = Date.parse(value);
  if (!Number.isFinite(ms)) throw new PriceSourceError(code, `${label} is not a valid timestamp`);
  return new Date(ms).toISOString();
}

function validateSlots(slots) {
  if (!Array.isArray(slots) || slots.length === 0) {
    throw new PriceSourceError('NO_SLOTS', 'price source contains no slots');
  }
  let previous = null;
  for (const slot of slots) {
    const current = Date.parse(slot.start);
    if (previous !== null) {
      const delta = current - previous;
      if (delta === 0) throw new PriceSourceError('DUPLICATE_TIMESTAMP', `duplicate timestamp ${slot.start}`);
      if (delta !== FIFTEEN_MIN_MS) throw new PriceSourceError('SLOT_GAP', `expected 15-minute cadence before ${slot.start}`);
    }
    previous = current;
  }
}

function localDateInZone(iso, timeZone = 'Europe/Amsterdam') {
  const date = new Date(iso);
  if (!Number.isFinite(date.getTime())) throw new PriceSourceError('BAD_TIMESTAMP', `invalid timestamp ${iso}`);
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date);
  const map = Object.fromEntries(parts.filter(p => p.type !== 'literal').map(p => [p.type, p.value]));
  return `${map.year}-${map.month}-${map.day}`;
}

export function normalizeEnergyZeroRest(payload, options = {}) {
  const {
    retrievedAt = new Date().toISOString(),
    localDate = null,
    timeZone = 'Europe/Amsterdam',
    stream = 'base',
    priceBasis = stream === 'base' ? 'MARKET_EX_VAT' : 'SOURCE_STREAM_UNKNOWN',
  } = options;

  if (!payload || typeof payload !== 'object') {
    throw new PriceSourceError('BAD_PAYLOAD', 'EnergyZero REST payload must be an object');
  }
  if (!Array.isArray(payload[stream])) {
    throw new PriceSourceError('BAD_SCHEMA', `EnergyZero REST payload.${stream} must be an array`);
  }

  let sourceRows = payload[stream];
  if (localDate) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(localDate)) {
      throw new PriceSourceError('BAD_LOCAL_DATE', `localDate must be YYYY-MM-DD, got ${localDate}`);
    }
    sourceRows = sourceRows.filter(row => row?.start && localDateInZone(row.start, timeZone) === localDate);
  }

  const slots = sourceRows.map((row, index) => {
    if (!row || typeof row !== 'object') throw new PriceSourceError('BAD_SCHEMA', `${stream}[${index}] must be an object`);
    const start = toIso(row.start, 'BAD_TIMESTAMP', `${stream}[${index}].start`);
    const end = toIso(row.end, 'BAD_TIMESTAMP', `${stream}[${index}].end`);
    if (Date.parse(end) - Date.parse(start) !== FIFTEEN_MIN_MS) {
      throw new PriceSourceError('WRONG_RESOLUTION', `${stream}[${index}] is not a 15-minute slot`);
    }
    const marketPriceEurPerKwh = assertFiniteNumber(row?.price?.value, 'BAD_PRICE', `${stream}[${index}].price.value`);
    return {
      start,
      end,
      marketPriceEurPerKwh,
      importPriceEurPerKwh: null,
      exportPriceEurPerKwh: null,
      isForecast: false,
    };
  }).sort((a, b) => Date.parse(a.start) - Date.parse(b.start));

  validateSlots(slots);
  return {
    schemaVersion: 'price-source-v0.1',
    source: 'ENERGYZERO_PUBLIC_REST',
    biddingZone: NL_ZONE,
    currency: 'EUR',
    resolutionMinutes: 15,
    generatedAt: null,
    retrievedAt: toIso(retrievedAt, 'BAD_RETRIEVED_AT', 'retrievedAt'),
    priceBasis,
    slots,
    health: {
      valid: true,
      complete: localDate ? [92, 96, 100].includes(slots.length) : null,
      stale: false,
      horizonEnd: slots.at(-1).end,
    },
    sourceMeta: {
      api: 'https://public.api.energyzero.nl/public/v1/prices',
      stream,
      requestedLocalDate: localDate,
      timeZone,
      rawStreamCount: payload[stream].length,
    },
  };
}

// Legacy schema retained only for deterministic tests/backward compatibility.
export function normalizeEnergyZero(payload, options = {}) {
  const {
    retrievedAt = new Date().toISOString(),
    priceBasis = 'SOURCE_PRICE_UNKNOWN',
    expectedIntervalType = 3,
  } = options;

  if (!payload || typeof payload !== 'object') {
    throw new PriceSourceError('BAD_PAYLOAD', 'EnergyZero payload must be an object');
  }
  if (payload.intervalType != null && payload.intervalType !== expectedIntervalType) {
    throw new PriceSourceError('WRONG_RESOLUTION', `EnergyZero intervalType must be ${expectedIntervalType}`);
  }
  if (!Array.isArray(payload.Prices)) {
    throw new PriceSourceError('BAD_SCHEMA', 'EnergyZero payload.Prices must be an array');
  }

  const slots = payload.Prices.map((row, index) => {
    if (!row || typeof row !== 'object') throw new PriceSourceError('BAD_SCHEMA', `Prices[${index}] must be an object`);
    const start = toIso(row.readingDate, 'BAD_TIMESTAMP', `Prices[${index}].readingDate`);
    const marketPriceEurPerKwh = assertFiniteNumber(row.price, 'BAD_PRICE', `Prices[${index}].price`);
    return {
      start,
      end: new Date(Date.parse(start) + FIFTEEN_MIN_MS).toISOString(),
      marketPriceEurPerKwh,
      importPriceEurPerKwh: null,
      exportPriceEurPerKwh: null,
      isForecast: false,
    };
  }).sort((a, b) => Date.parse(a.start) - Date.parse(b.start));

  validateSlots(slots);
  const horizonEnd = slots.at(-1).end;
  return {
    schemaVersion: 'price-source-v0.1',
    source: 'ENERGYZERO_LEGACY',
    biddingZone: NL_ZONE,
    currency: 'EUR',
    resolutionMinutes: 15,
    generatedAt: null,
    retrievedAt: toIso(retrievedAt, 'BAD_RETRIEVED_AT', 'retrievedAt'),
    priceBasis,
    slots,
    health: {
      valid: true,
      complete: null,
      stale: false,
      horizonEnd,
    },
    sourceMeta: {
      intervalType: payload.intervalType ?? expectedIntervalType,
      fromDate: payload.fromDate ?? null,
      tillDate: payload.tillDate ?? null,
      average: typeof payload.average === 'number' && Number.isFinite(payload.average) ? payload.average : null,
    },
  };
}

export function normalizePbthInterApp(payload, options = {}) {
  const { retrievedAt = new Date().toISOString(), deviceId = null } = options;
  if (!payload || typeof payload !== 'object' || !Array.isArray(payload.prices)) {
    throw new PriceSourceError('BAD_SCHEMA', 'PBTH payload.prices must be an array');
  }

  const candidates = payload.prices.filter(p =>
    p && p.driverType === 'dap15' && p.biddingZone === NL_ZONE && p.priceInterval === 15 && (!deviceId || p.deviceId === deviceId));
  if (candidates.length !== 1) {
    throw new PriceSourceError('PBTH_DEVICE_SELECTION', `expected exactly one NL dap15 device, got ${candidates.length}`);
  }
  const selected = candidates[0];
  const slots = selected.slots.map((row, index) => {
    const start = toIso(row.time, 'BAD_TIMESTAMP', `slots[${index}].time`);
    const importPrice = assertFiniteNumber(row.importPrice, 'BAD_PRICE', `slots[${index}].importPrice`);
    return {
      start,
      end: new Date(Date.parse(start) + FIFTEEN_MIN_MS).toISOString(),
      marketPriceEurPerKwh: null,
      importPriceEurPerKwh: importPrice,
      exportPriceEurPerKwh: typeof row.exportPrice === 'number' && Number.isFinite(row.exportPrice) ? row.exportPrice : null,
      isForecast: Boolean(row.isForecast),
    };
  }).sort((a, b) => Date.parse(a.start) - Date.parse(b.start));

  validateSlots(slots);
  return {
    schemaVersion: 'price-source-v0.1',
    source: 'PBTH_INTERAPP_DAP_PRICES',
    biddingZone: NL_ZONE,
    currency: selected.currency || 'EUR',
    resolutionMinutes: 15,
    generatedAt: payload.generatedAt ? toIso(payload.generatedAt, 'BAD_GENERATED_AT', 'generatedAt') : null,
    retrievedAt: toIso(retrievedAt, 'BAD_RETRIEVED_AT', 'retrievedAt'),
    priceBasis: 'CONTRACT_IMPORT_UNKNOWN',
    slots,
    health: { valid: true, complete: null, stale: false, horizonEnd: slots.at(-1).end },
    sourceMeta: { deviceId: selected.deviceId, deviceName: selected.deviceName, driverType: selected.driverType },
  };
}

export function compareByTimestamp(left, right, options = {}) {
  const { leftField = 'marketPriceEurPerKwh', rightField = 'marketPriceEurPerKwh' } = options;
  const rightByStart = new Map(right.slots.map(slot => [slot.start, slot]));
  const rows = [];
  for (const l of left.slots) {
    const r = rightByStart.get(l.start);
    if (!r) continue;
    const lv = l[leftField];
    const rv = r[rightField];
    rows.push({
      timestamp: l.start,
      left: lv,
      right: rv,
      delta: typeof lv === 'number' && typeof rv === 'number' ? lv - rv : null,
    });
  }
  return {
    overlapCount: rows.length,
    leftCount: left.slots.length,
    rightCount: right.slots.length,
    rows,
  };
}
