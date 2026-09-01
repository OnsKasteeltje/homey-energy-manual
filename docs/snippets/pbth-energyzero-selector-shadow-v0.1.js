// PBTH + EnergyZero Price Source Selector v0.1 — SHADOW / READ-ONLY
// Doel: live beide bronnen uitlezen, semantiek/horizon valideren en compact tonen
// welke bron de selector zou kiezen. Geen Logic-writes, geen device-writes,
// geen productie-cutover.

const SCHEMA = 'EM2_PRICE_SOURCE_SELECTOR_LIVE_SHADOW_V0.1';
const NL_ZONE = '10YNL----------L';
const SLOT_MINUTES = 15;
const SLOT_MS = SLOT_MINUTES * 60 * 1000;
const TIME_ZONE = 'Europe/Amsterdam';
const REQUIRED_BASIS = 'MARKET_EX_VAT';

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

function validateCadence(slots, label) {
  for (let i = 0; i < slots.length; i += 1) {
    const slot = slots[i];
    if (slot.endMs - slot.startMs !== SLOT_MS) {
      throw new Error(`${label} verkeerde slotduur op index ${i}`);
    }
    if (i > 0 && slot.startMs - slots[i - 1].startMs !== SLOT_MS) {
      throw new Error(`${label} slot gap/duplicate op index ${i}`);
    }
  }
}

function readPbth(data) {
  if (!data || !Array.isArray(data.prices)) throw new Error('PBTH response bevat geen prices-array');
  const candidates = data.prices.filter((device) =>
    device && device.driverType === 'dap15' && device.priceInterval === SLOT_MINUTES && device.biddingZone === NL_ZONE
  );
  if (candidates.length !== 1) throw new Error(`PBTH verwacht exact 1 NL dap15-device; gevonden: ${candidates.length}`);
  const device = candidates[0];
  if (!Array.isArray(device.slots) || device.slots.length === 0) throw new Error('PBTH dap15-device bevat geen slots');

  const slots = device.slots.map((slot, index) => {
    const startMs = isoMs(slot?.time);
    const price = finiteNumber(slot?.importPrice);
    if (startMs === null) throw new Error(`PBTH invalid time op index ${index}`);
    if (price === null) throw new Error(`PBTH invalid importPrice op index ${index}`);
    if (typeof slot?.isForecast !== 'boolean') throw new Error(`PBTH invalid isForecast op index ${index}`);
    return {
      startMs,
      endMs: startMs + SLOT_MS,
      price,
      isForecast: slot.isForecast,
    };
  }).sort((a, b) => a.startMs - b.startMs);

  validateCadence(slots, 'PBTH');
  return { device, slots };
}

function readEnergyZeroBase(payload) {
  const rows = payload?.base;
  if (!Array.isArray(rows) || rows.length === 0) throw new Error('EnergyZero base ontbreekt/leeg');
  const slots = rows.map((row, index) => {
    const startMs = isoMs(row?.start);
    const endMs = isoMs(row?.end);
    const price = finiteNumber(row?.price?.value);
    if (startMs === null || endMs === null) throw new Error(`EnergyZero invalid timestamp op index ${index}`);
    if (price === null) throw new Error(`EnergyZero invalid price op index ${index}`);
    return { startMs, endMs, price };
  }).sort((a, b) => a.startMs - b.startMs);
  validateCadence(slots, 'EnergyZero');
  return slots;
}

function overlapExact(pbthSlots, ezSlots) {
  const ezMap = new Map(ezSlots.map((s) => [s.startMs, s.price]));
  let overlap = 0;
  let exact = 0;
  let maxAbsDelta = 0;
  for (const slot of pbthSlots) {
    if (!ezMap.has(slot.startMs)) continue;
    overlap += 1;
    const delta = Math.abs(slot.price - ezMap.get(slot.startMs));
    if (delta <= 1e-12) exact += 1;
    if (delta > maxAbsDelta) maxAbsDelta = delta;
  }
  return { overlap, exact, maxAbsDelta };
}

function evaluate(source, requiredHorizonMs, nowMs) {
  const reasons = [];
  if (source.biddingZone !== NL_ZONE) reasons.push('BAD_BIDDING_ZONE');
  if (source.resolutionMinutes !== SLOT_MINUTES) reasons.push('BAD_RESOLUTION');
  if (source.priceBasis !== REQUIRED_BASIS) reasons.push('BAD_PRICE_BASIS');
  if (!source.slots.length) reasons.push('NO_SLOTS');
  if (source.horizonEndMs < requiredHorizonMs) reasons.push('HORIZON_TOO_SHORT');
  if (nowMs - source.retrievedAtMs > 30 * 60 * 1000) reasons.push('RETRIEVAL_TOO_OLD');
  return { eligible: reasons.length === 0, reasons };
}

try {
  const generatedAt = new Date().toISOString();
  const nowMs = Date.parse(generatedAt);
  const requestedLocalDate = localDate();

  // Planner-horizon shadow target: require at least 24h forward from current instant.
  const requiredHorizonMs = nowMs + (24 * 60 * 60 * 1000);
  const requiredHorizonEnd = new Date(requiredHorizonMs).toISOString();

  // PBTH Inter-App read.
  const pbthApp = await Homey.apps.getApp({ id: 'com.gruijter.powerhour' });
  const pbthRaw = await pbthApp.get({ path: '/dap-prices' });
  const { device, slots: pbthSlots } = readPbth(pbthRaw);

  // EnergyZero public REST read.
  const ezDate = energyZeroDateParam(requestedLocalDate);
  const ezUrl = `https://public.api.energyzero.nl/public/v1/prices?energyType=ENERGY_TYPE_ELECTRICITY&date=${encodeURIComponent(ezDate)}&interval=INTERVAL_QUARTER`;
  const response = await fetch(ezUrl);
  if (!response.ok) throw new Error(`EnergyZero HTTP ${response.status}`);
  const ezRaw = await response.json();
  const ezSlots = readEnergyZeroBase(ezRaw);

  // Current PBTH semantics were live validated 2026-09-01: 109/109 exact vs EZ base.
  // Reconfirm every run before making PBTH eligible as MARKET_EX_VAT in shadow.
  const ab = overlapExact(pbthSlots, ezSlots);
  const pbthSemanticsConfirmed = ab.overlap > 0 && ab.exact === ab.overlap && ab.maxAbsDelta <= 1e-12;

  const energyZeroSource = {
    source: 'ENERGYZERO_PUBLIC_REST',
    biddingZone: NL_ZONE,
    resolutionMinutes: SLOT_MINUTES,
    priceBasis: REQUIRED_BASIS,
    slots: ezSlots,
    horizonEndMs: ezSlots[ezSlots.length - 1].endMs,
    retrievedAtMs: nowMs,
  };

  const pbthSource = {
    source: 'PBTH_INTERAPP_DAP_PRICES',
    biddingZone: device.biddingZone,
    resolutionMinutes: device.priceInterval,
    priceBasis: pbthSemanticsConfirmed ? REQUIRED_BASIS : 'UNCONFIRMED',
    slots: pbthSlots,
    horizonEndMs: pbthSlots[pbthSlots.length - 1].endMs,
    retrievedAtMs: nowMs,
  };

  const ezEval = evaluate(energyZeroSource, requiredHorizonMs, nowMs);
  const pbthEval = evaluate(pbthSource, requiredHorizonMs, nowMs);

  let selectedSource = null;
  if (ezEval.eligible) selectedSource = energyZeroSource.source;
  else if (pbthEval.eligible) selectedSource = pbthSource.source;

  const result = {
    schema: SCHEMA,
    status: selectedSource ? 'OK' : 'NO_ELIGIBLE_SOURCE',
    generatedAt,
    mode: 'SHADOW_READ_ONLY',
    requestedLocalDate,
    requiredHorizonEnd,
    selectedSource,
    productionSwitchAllowed: false,
    abValidation: {
      overlapSlots: ab.overlap,
      exactMatchSlots: ab.exact,
      maxAbsDelta: ab.maxAbsDelta,
      pbthMarketExVatConfirmedThisRun: pbthSemanticsConfirmed,
    },
    energyZero: {
      eligible: ezEval.eligible,
      reasons: ezEval.reasons,
      slotCount: ezSlots.length,
      firstSlot: new Date(ezSlots[0].startMs).toISOString(),
      horizonEnd: new Date(energyZeroSource.horizonEndMs).toISOString(),
      priceBasis: energyZeroSource.priceBasis,
    },
    pbth: {
      eligible: pbthEval.eligible,
      reasons: pbthEval.reasons,
      deviceId: device.deviceId ?? null,
      slotCount: pbthSlots.length,
      confirmedSlotCount: pbthSlots.filter((s) => !s.isForecast).length,
      forecastSlotCount: pbthSlots.filter((s) => s.isForecast).length,
      firstSlot: new Date(pbthSlots[0].startMs).toISOString(),
      horizonEnd: new Date(pbthSource.horizonEndMs).toISOString(),
      priceBasis: pbthSource.priceBasis,
    },
    selectorPolicy: 'ENERGYZERO_PRIMARY_PBTH_SECONDARY_SHADOW',
  };

  log(JSON.stringify(result, null, 2));
  return result;
} catch (err) {
  const result = {
    schema: SCHEMA,
    status: 'ERROR',
    generatedAt: new Date().toISOString(),
    mode: 'SHADOW_READ_ONLY',
    productionSwitchAllowed: false,
    error: String(err?.message || err),
  };
  log(JSON.stringify(result, null, 2));
  return result;
}
