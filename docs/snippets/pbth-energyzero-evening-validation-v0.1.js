// PBTH ↔ EnergyZero Evening Validation v0.1 — SHADOW / READ-ONLY
// Intended for a single evening run after next-day prices should be available.
// No Logic writes. No device writes. No production cutover.

const SCHEMA = 'EM2_PRICE_SOURCE_EVENING_VALIDATION_V0.1';
const NL_ZONE = '10YNL----------L';
const SLOT_MINUTES = 15;
const SLOT_MS = SLOT_MINUTES * 60 * 1000;
const TIME_ZONE = 'Europe/Amsterdam';
const EXACT_EPSILON = 1e-12;

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

function addDays(localDateString, days) {
  const [y, m, d] = localDateString.split('-').map(Number);
  const date = new Date(Date.UTC(y, m - 1, d + days, 12, 0, 0));
  return date.toISOString().slice(0, 10);
}

function energyZeroDateParam(yyyyMmDd) {
  const [y, m, d] = yyyyMmDd.split('-');
  return `${d}-${m}-${y}`;
}

function localDateOfIso(iso) {
  return localDate(new Date(iso));
}

function validatePbth(data) {
  if (!data || !Array.isArray(data.prices)) throw new Error('PBTH response bevat geen prices-array');
  const candidates = data.prices.filter((device) =>
    device && device.driverType === 'dap15' && device.priceInterval === SLOT_MINUTES && device.biddingZone === NL_ZONE
  );
  if (candidates.length !== 1) throw new Error(`PBTH verwacht exact 1 NL dap15-device; gevonden: ${candidates.length}`);
  const device = candidates[0];
  if (!Array.isArray(device.slots) || device.slots.length === 0) throw new Error('PBTH dap15-device bevat geen slots');
  const slots = device.slots.map((slot, index) => {
    const ms = isoMs(slot?.time);
    const importPrice = finiteNumber(slot?.importPrice);
    if (ms === null) throw new Error(`PBTH invalid time op index ${index}`);
    if (importPrice === null) throw new Error(`PBTH invalid importPrice op index ${index}`);
    return {
      time: new Date(ms).toISOString(),
      ms,
      importPrice,
      isForecast: slot?.isForecast === true,
    };
  }).sort((a, b) => a.ms - b.ms);
  for (let i = 1; i < slots.length; i += 1) {
    if (slots[i].ms - slots[i - 1].ms !== SLOT_MS) throw new Error(`PBTH slot gap op index ${i}`);
  }
  return { device, slots };
}

function validateEnergyZeroBase(payload) {
  const rows = payload?.base;
  if (!Array.isArray(rows) || rows.length === 0) throw new Error('EnergyZero base ontbreekt/leeg');
  const slots = rows.map((row, index) => {
    const ms = isoMs(row?.start);
    const endMs = isoMs(row?.end);
    const price = finiteNumber(row?.price?.value);
    if (ms === null || endMs === null) throw new Error(`EnergyZero invalid timestamp op index ${index}`);
    if (endMs - ms !== SLOT_MS) throw new Error(`EnergyZero geen 15-min slot op index ${index}`);
    if (price === null) throw new Error(`EnergyZero invalid price op index ${index}`);
    return { time: new Date(ms).toISOString(), ms, price };
  }).sort((a, b) => a.ms - b.ms);
  for (let i = 1; i < slots.length; i += 1) {
    if (slots[i].ms - slots[i - 1].ms !== SLOT_MS) throw new Error(`EnergyZero slot gap op index ${i}`);
  }
  return slots;
}

function summarizeLocalDay(slots, targetDate, field) {
  const daySlots = slots.filter((slot) => localDateOfIso(slot.time) === targetDate);
  const values = daySlots.map((slot) => slot[field]);
  return {
    date: targetDate,
    slotCount: daySlots.length,
    complete96: daySlots.length === 96,
    firstSlot: daySlots[0]?.time ?? null,
    lastSlot: daySlots[daySlots.length - 1]?.time ?? null,
    min: values.length ? Math.min(...values) : null,
    avg: values.length ? values.reduce((a, b) => a + b, 0) / values.length : null,
    max: values.length ? Math.max(...values) : null,
  };
}

function compare(pbthSlots, ezSlots) {
  const ezMap = new Map(ezSlots.map((s) => [s.time, s.price]));
  let overlapSlots = 0;
  let exactMatchSlots = 0;
  let maxAbsDelta = 0;
  for (const slot of pbthSlots) {
    if (!ezMap.has(slot.time)) continue;
    overlapSlots += 1;
    const delta = Math.abs(slot.importPrice - ezMap.get(slot.time));
    if (delta <= EXACT_EPSILON) exactMatchSlots += 1;
    if (delta > maxAbsDelta) maxAbsDelta = delta;
  }
  return { overlapSlots, exactMatchSlots, maxAbsDelta, exact: overlapSlots > 0 && exactMatchSlots === overlapSlots };
}

try {
  const generatedAt = new Date().toISOString();
  const today = localDate();
  const tomorrow = addDays(today, 1);

  const pbthApp = await Homey.apps.getApp({ id: 'com.gruijter.powerhour' });
  const pbthRaw = await pbthApp.get({ path: '/dap-prices' });
  const { device, slots: pbthSlots } = validatePbth(pbthRaw);

  const ezDate = energyZeroDateParam(today);
  const ezUrl = `https://public.api.energyzero.nl/public/v1/prices?energyType=ENERGY_TYPE_ELECTRICITY&date=${encodeURIComponent(ezDate)}&interval=INTERVAL_QUARTER`;
  const response = await fetch(ezUrl);
  if (!response.ok) throw new Error(`EnergyZero HTTP ${response.status}`);
  const ezSlots = validateEnergyZeroBase(await response.json());

  const pbthTomorrow = summarizeLocalDay(pbthSlots, tomorrow, 'importPrice');
  const ezTomorrow = summarizeLocalDay(ezSlots, tomorrow, 'price');
  const ab = compare(pbthSlots, ezSlots);

  const energyZeroTomorrowReady = ezTomorrow.complete96;
  const pbthTomorrowReady = pbthTomorrow.complete96;
  const semanticMatch = ab.exact;

  let verdict = 'PASS';
  const findings = [];

  if (!energyZeroTomorrowReady) {
    verdict = 'FAIL';
    findings.push('ENERGYZERO_TOMORROW_INCOMPLETE');
  }
  if (!semanticMatch) {
    verdict = 'FAIL';
    findings.push('PBTH_ENERGYZERO_PRICE_MISMATCH');
  }
  if (!pbthTomorrowReady && energyZeroTomorrowReady) {
    findings.push('PBTH_LAGS_WHILE_ENERGYZERO_READY');
  }
  if (pbthTomorrowReady && energyZeroTomorrowReady) {
    findings.push('BOTH_SOURCES_TOMORROW_READY');
  }

  const selectorWouldChoose = energyZeroTomorrowReady ? 'ENERGYZERO_PUBLIC_REST' : (pbthTomorrowReady && semanticMatch ? 'PBTH_INTERAPP_DAP_PRICES' : null);

  const result = {
    schema: SCHEMA,
    status: 'OK',
    verdict,
    generatedAt,
    mode: 'SHADOW_READ_ONLY',
    today,
    tomorrow,
    selectorWouldChoose,
    productionSwitchAllowed: false,
    findings,
    energyZero: {
      source: 'ENERGYZERO_PUBLIC_REST',
      priceBasis: 'MARKET_EX_VAT',
      totalSlotsReturned: ezSlots.length,
      horizonEnd: ezSlots[ezSlots.length - 1]?.time ?? null,
      tomorrow: ezTomorrow,
    },
    pbth: {
      source: 'PBTH_INTERAPP_DAP_PRICES',
      deviceId: device.deviceId ?? null,
      totalSlotsReturned: pbthSlots.length,
      confirmedSlotCount: pbthSlots.filter((s) => !s.isForecast).length,
      forecastSlotCount: pbthSlots.filter((s) => s.isForecast).length,
      horizonEnd: pbthSlots[pbthSlots.length - 1]?.time ?? null,
      tomorrow: pbthTomorrow,
    },
    abValidation: ab,
    interpretation: !energyZeroTomorrowReady
      ? 'FAIL: EnergyZero heeft morgenavond geen complete volgende lokale dag.'
      : !semanticMatch
        ? 'FAIL: PBTH en EnergyZero verschillen op overlappende kwartieren.'
        : !pbthTomorrowReady
          ? 'PASS: EnergyZero heeft morgen compleet terwijl PBTH achterloopt; redundante bron/selector vangt precies dit scenario op.'
          : 'PASS: EnergyZero en PBTH hebben morgen beide compleet en overlappende prijzen zijn gelijk.',
  };

  log(JSON.stringify(result, null, 2));
  return result;
} catch (err) {
  const result = {
    schema: SCHEMA,
    status: 'ERROR',
    verdict: 'FAIL',
    generatedAt: new Date().toISOString(),
    mode: 'SHADOW_READ_ONLY',
    error: String(err?.message || err),
    productionSwitchAllowed: false,
  };
  log(JSON.stringify(result, null, 2));
  return result;
}
