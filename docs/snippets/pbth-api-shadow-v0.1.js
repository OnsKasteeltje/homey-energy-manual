// PBTH API Adapter v0.1 — SHADOW / READ-ONLY
// Doel: valideer de lokale PBTH DAP15 API zonder Logic- of devicewrites.
// Broncontract: PBTH inter-app GET /dap-prices via Homey.apps.getApp().

const SCHEMA = 'EM2_PBTH_API_SHADOW_V0.1';
const NL_ZONE = '10YNL----------L';
const SLOT_MINUTES = 15;
const SLOT_MS = SLOT_MINUTES * 60 * 1000;
const EPS = 1000; // 1 s tolerantie op timestampverschillen

function isFiniteNumber(v) {
  return typeof v === 'number' && Number.isFinite(v);
}

function isoMs(value) {
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}

function fail(code, detail, extra = {}) {
  return {
    schema: SCHEMA,
    status: 'ERROR',
    generatedAt: new Date().toISOString(),
    errors: [{ code, detail }],
    ...extra,
  };
}

let data;
try {
  const pbth = await Homey.apps.getApp({ id: 'com.gruijter.powerhour' });
  data = await pbth.get({ path: '/dap-prices' });
} catch (err) {
  const result = fail('PBTH_API_ERROR', String(err?.message || err));
  log(JSON.stringify(result, null, 2));
  return result;
}

if (!data || !Array.isArray(data.prices)) {
  const result = fail('INVALID_RESPONSE', 'PBTH response bevat geen prices-array');
  log(JSON.stringify(result, null, 2));
  return result;
}

const candidates = data.prices.filter((device) =>
  device &&
  device.driverType === 'dap15' &&
  device.priceInterval === SLOT_MINUTES &&
  device.biddingZone === NL_ZONE
);

if (candidates.length === 0) {
  const result = fail('NO_DAP15_DEVICE', 'Geen NL DAP15-device gevonden', {
    discoveredDevices: data.prices.map((d) => ({
      deviceId: d?.deviceId ?? null,
      deviceName: d?.deviceName ?? null,
      driverType: d?.driverType ?? null,
      biddingZone: d?.biddingZone ?? null,
      priceInterval: d?.priceInterval ?? null,
    })),
  });
  log(JSON.stringify(result, null, 2));
  return result;
}

if (candidates.length > 1) {
  const result = fail('AMBIGUOUS_DAP15_DEVICE', 'Meer dan één NL DAP15-device matcht; expliciete selectie vereist', {
    candidates: candidates.map((d) => ({ deviceId: d.deviceId, deviceName: d.deviceName })),
  });
  log(JSON.stringify(result, null, 2));
  return result;
}

const device = candidates[0];
if (!Array.isArray(device.slots) || device.slots.length === 0) {
  const result = fail('NO_SLOTS', 'DAP15-device bevat geen toekomstige slots', {
    deviceId: device.deviceId,
    deviceName: device.deviceName,
  });
  log(JSON.stringify(result, null, 2));
  return result;
}

const errors = [];
const normalized = [];
let prevMs = null;

for (let i = 0; i < device.slots.length; i += 1) {
  const slot = device.slots[i] || {};
  const ms = isoMs(slot.time);

  if (ms === null) {
    errors.push({ code: 'INVALID_TIME', index: i, value: slot.time ?? null });
    continue;
  }
  if (!isFiniteNumber(slot.importPrice)) {
    errors.push({ code: 'INVALID_IMPORT_PRICE', index: i, value: slot.importPrice ?? null });
  }
  if (!isFiniteNumber(slot.exportPrice)) {
    errors.push({ code: 'INVALID_EXPORT_PRICE', index: i, value: slot.exportPrice ?? null });
  }
  if (typeof slot.isForecast !== 'boolean') {
    errors.push({ code: 'INVALID_FORECAST_FLAG', index: i, value: slot.isForecast ?? null });
  }

  if (prevMs !== null) {
    const delta = ms - prevMs;
    if (delta <= 0) {
      errors.push({ code: 'NON_MONOTONIC_TIME', index: i, deltaMs: delta });
    } else if (Math.abs(delta - SLOT_MS) > EPS) {
      errors.push({ code: 'SLOT_GAP', index: i, deltaMs: delta, expectedMs: SLOT_MS });
    }
  }
  prevMs = ms;

  normalized.push({
    time: new Date(ms).toISOString(),
    importPrice: slot.importPrice,
    exportPrice: slot.exportPrice,
    isForecast: slot.isForecast,
  });
}

if (errors.length > 0) {
  const result = {
    schema: SCHEMA,
    status: 'ERROR',
    generatedAt: data.generatedAt ?? new Date().toISOString(),
    deviceId: device.deviceId ?? null,
    deviceName: device.deviceName ?? null,
    errors,
  };
  log(JSON.stringify(result, null, 2));
  return result;
}

const lastMs = isoMs(normalized[normalized.length - 1].time);
const horizonHours = lastMs !== null
  ? ((lastMs + SLOT_MS) - Date.now()) / 3600000
  : null;

const confirmedSlotCount = normalized.filter((s) => s.isForecast === false).length;
const forecastSlotCount = normalized.filter((s) => s.isForecast === true).length;

const result = {
  schema: SCHEMA,
  status: 'OK',
  generatedAt: data.generatedAt ?? new Date().toISOString(),
  deviceId: device.deviceId ?? null,
  deviceName: device.deviceName ?? null,
  biddingZone: device.biddingZone ?? null,
  currency: device.currency ?? null,
  priceInterval: device.priceInterval ?? null,
  slotCount: normalized.length,
  confirmedSlotCount,
  forecastSlotCount,
  firstSlot: normalized[0].time,
  lastSlot: normalized[normalized.length - 1].time,
  horizonHours: horizonHours === null ? null : Number(horizonHours.toFixed(3)),
  currentImportPrice: normalized[0].importPrice,
  currentExportPrice: normalized[0].exportPrice,
  slots: normalized,
  errors: [],
};

log(JSON.stringify(result, null, 2));
return result;
