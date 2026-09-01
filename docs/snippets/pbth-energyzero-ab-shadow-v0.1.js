// PBTH ↔ EnergyZero A/B v0.1 — SHADOW / READ-ONLY
// Doel: vergelijk PBTH DAP15 direct met de vier EnergyZero prijsstreams
// zonder grote slot-arrays uit HomeyScript te hoeven kopiëren.
//
// Geen Logic-writes. Geen device-writes. Geen productie-cutover.
// Output is uitsluitend een compacte diagnostische samenvatting.

const SCHEMA = 'EM2_PRICE_SOURCE_AB_SHADOW_V0.1';
const NL_ZONE = '10YNL----------L';
const SLOT_MINUTES = 15;
const SLOT_MS = SLOT_MINUTES * 60 * 1000;
const TIME_ZONE = 'Europe/Amsterdam';

function finiteNumber(value) {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function isoMs(value) {
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}

function localDate(date = new Date(), timeZone = TIME_ZONE) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date);
  const get = (type) => parts.find((p) => p.type === type)?.value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}

function energyZeroDateParam(yyyyMmDd) {
  const [y, m, d] = yyyyMmDd.split('-');
  return `${d}-${m}-${y}`;
}

function stats(values) {
  if (!values.length) return null;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const abs = values.map((v) => Math.abs(v));
  const meanAbs = abs.reduce((a, b) => a + b, 0) / abs.length;
  const rms = Math.sqrt(values.reduce((a, b) => a + (b * b), 0) / values.length);
  const variance = values.reduce((a, b) => a + ((b - mean) ** 2), 0) / values.length;
  const stddev = Math.sqrt(variance);
  return {
    n: values.length,
    meanDelta: Number(mean.toFixed(9)),
    meanAbsDelta: Number(meanAbs.toFixed(9)),
    rmsDelta: Number(rms.toFixed(9)),
    stddevDelta: Number(stddev.toFixed(9)),
    minDelta: Number(Math.min(...values).toFixed(9)),
    maxDelta: Number(Math.max(...values).toFixed(9)),
  };
}

function validatePbth(data) {
  if (!data || !Array.isArray(data.prices)) {
    throw new Error('PBTH response bevat geen prices-array');
  }

  const candidates = data.prices.filter((device) =>
    device &&
    device.driverType === 'dap15' &&
    device.priceInterval === SLOT_MINUTES &&
    device.biddingZone === NL_ZONE
  );

  if (candidates.length !== 1) {
    throw new Error(`PBTH verwacht exact 1 NL dap15-device; gevonden: ${candidates.length}`);
  }

  const device = candidates[0];
  if (!Array.isArray(device.slots) || device.slots.length === 0) {
    throw new Error('PBTH dap15-device bevat geen slots');
  }

  const slots = device.slots.map((slot, index) => {
    const ms = isoMs(slot?.time);
    const importPrice = finiteNumber(slot?.importPrice);
    const exportPrice = finiteNumber(slot?.exportPrice);
    if (ms === null) throw new Error(`PBTH invalid time op index ${index}`);
    if (importPrice === null) throw new Error(`PBTH invalid importPrice op index ${index}`);
    if (exportPrice === null) throw new Error(`PBTH invalid exportPrice op index ${index}`);
    if (typeof slot?.isForecast !== 'boolean') throw new Error(`PBTH invalid isForecast op index ${index}`);
    return {
      time: new Date(ms).toISOString(),
      ms,
      importPrice,
      exportPrice,
      isForecast: slot.isForecast,
    };
  }).sort((a, b) => a.ms - b.ms);

  for (let i = 1; i < slots.length; i += 1) {
    const delta = slots[i].ms - slots[i - 1].ms;
    if (delta !== SLOT_MS) {
      throw new Error(`PBTH slot gap op index ${i}: ${delta} ms`);
    }
  }

  return { device, slots };
}

function energyZeroMaps(payload) {
  const definitions = [
    ['base', 'MARKET_EX_VAT'],
    ['base_with_vat', 'MARKET_WITH_VAT'],
    ['all_in', 'ALL_IN_EX_VAT'],
    ['all_in_with_vat', 'ALL_IN_WITH_VAT'],
  ];

  const result = {};
  for (const [stream, basis] of definitions) {
    const rows = payload?.[stream];
    if (!Array.isArray(rows) || rows.length === 0) {
      throw new Error(`EnergyZero stream ontbreekt/leeg: ${stream}`);
    }
    const map = new Map();
    for (let i = 0; i < rows.length; i += 1) {
      const row = rows[i];
      const ms = isoMs(row?.start);
      const endMs = isoMs(row?.end);
      const value = finiteNumber(row?.price?.value);
      if (ms === null || endMs === null) throw new Error(`EnergyZero invalid timestamp in ${stream}[${i}]`);
      if ((endMs - ms) !== SLOT_MS) throw new Error(`EnergyZero geen 15-min slot in ${stream}[${i}]`);
      if (value === null) throw new Error(`EnergyZero invalid price in ${stream}[${i}]`);
      map.set(new Date(ms).toISOString(), value);
    }
    result[stream] = { basis, rawSlots: rows.length, map };
  }
  return result;
}

function compare(pbthSlots, ez) {
  const deltasAll = [];
  const deltasConfirmed = [];
  const deltasForecast = [];

  for (const slot of pbthSlots) {
    if (!ez.map.has(slot.time)) continue;
    const delta = slot.importPrice - ez.map.get(slot.time);
    deltasAll.push(delta);
    if (slot.isForecast) deltasForecast.push(delta);
    else deltasConfirmed.push(delta);
  }

  return {
    basis: ez.basis,
    energyZeroRawSlots: ez.rawSlots,
    overlapSlots: deltasAll.length,
    all: stats(deltasAll),
    confirmed: stats(deltasConfirmed),
    forecast: stats(deltasForecast),
  };
}

try {
  // 1) PBTH lokaal uitlezen via Inter-App API.
  const pbthApp = await Homey.apps.getApp({ id: 'com.gruijter.powerhour' });
  const pbthRaw = await pbthApp.get({ path: '/dap-prices' });
  const { device, slots: pbthSlots } = validatePbth(pbthRaw);

  // 2) EnergyZero publieke REST uitlezen voor lokale datum.
  // De API levert momenteel een bredere window; vergelijking gebeurt exact op timestamp.
  const requestedLocalDate = localDate();
  const ezDate = energyZeroDateParam(requestedLocalDate);
  const ezUrl = `https://public.api.energyzero.nl/public/v1/prices?energyType=ENERGY_TYPE_ELECTRICITY&date=${encodeURIComponent(ezDate)}&interval=INTERVAL_QUARTER`;

  const response = await fetch(ezUrl);
  if (!response.ok) {
    throw new Error(`EnergyZero HTTP ${response.status}`);
  }
  const ezRaw = await response.json();
  const ez = energyZeroMaps(ezRaw);

  // 3) Vier prijssemantieken naast PBTH leggen.
  const comparisons = {};
  for (const stream of Object.keys(ez)) {
    comparisons[stream] = compare(pbthSlots, ez[stream]);
  }

  const ranked = Object.entries(comparisons)
    .filter(([, value]) => value.all && value.overlapSlots > 0)
    .sort((a, b) => {
      const sd = a[1].all.stddevDelta - b[1].all.stddevDelta;
      if (sd !== 0) return sd;
      return a[1].all.meanAbsDelta - b[1].all.meanAbsDelta;
    });

  const result = {
    schema: SCHEMA,
    status: 'OK',
    generatedAt: new Date().toISOString(),
    mode: 'SHADOW_READ_ONLY',
    requestedLocalDate,
    pbth: {
      deviceId: device.deviceId ?? null,
      deviceName: device.deviceName ?? null,
      biddingZone: device.biddingZone ?? null,
      currency: device.currency ?? null,
      slotCount: pbthSlots.length,
      confirmedSlotCount: pbthSlots.filter((s) => !s.isForecast).length,
      forecastSlotCount: pbthSlots.filter((s) => s.isForecast).length,
      firstSlot: pbthSlots[0]?.time ?? null,
      lastSlot: pbthSlots[pbthSlots.length - 1]?.time ?? null,
    },
    energyZero: {
      endpoint: 'public.api.energyzero.nl/public/v1/prices',
      interval: 'INTERVAL_QUARTER',
      streams: Object.fromEntries(Object.entries(ez).map(([k, v]) => [k, v.rawSlots])),
    },
    comparisons,
    closestShapeStream: ranked[0]?.[0] ?? null,
    diagnosticNote: 'closestShapeStream is alleen diagnostisch; geen automatische semantische gelijkstelling of failover.',
  };

  log(JSON.stringify(result, null, 2));
  return result;
} catch (err) {
  const result = {
    schema: SCHEMA,
    status: 'ERROR',
    generatedAt: new Date().toISOString(),
    mode: 'SHADOW_READ_ONLY',
    error: String(err?.message || err),
  };
  log(JSON.stringify(result, null, 2));
  return result;
}
