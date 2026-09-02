// Price Source DST helper v0.1
// Pure deterministic Europe/Amsterdam local-day slot validation.

const FIFTEEN_MIN_MS = 15 * 60 * 1000;

function localDateInZone(iso, timeZone = 'Europe/Amsterdam') {
  const date = new Date(iso);
  if (!Number.isFinite(date.getTime())) throw new Error(`invalid timestamp ${iso}`);
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date);
  const map = Object.fromEntries(parts.filter((p) => p.type !== 'literal').map((p) => [p.type, p.value]));
  return `${map.year}-${map.month}-${map.day}`;
}

export function expectedQuarterHourSlotsForLocalDate(localDate, timeZone = 'Europe/Amsterdam') {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(localDate)) throw new Error(`localDate must be YYYY-MM-DD, got ${localDate}`);
  const [year, month, day] = localDate.split('-').map(Number);
  const utcAnchor = Date.UTC(year, month - 1, day);
  let count = 0;
  // Wide UTC window safely covers the local day for European DST offsets.
  for (let ms = utcAnchor - 14 * 60 * 60 * 1000; ms < utcAnchor + 38 * 60 * 60 * 1000; ms += FIFTEEN_MIN_MS) {
    if (localDateInZone(new Date(ms).toISOString(), timeZone) === localDate) count += 1;
  }
  return count;
}

export function validateLocalDaySlots(slots, localDate, timeZone = 'Europe/Amsterdam') {
  const expected = expectedQuarterHourSlotsForLocalDate(localDate, timeZone);
  const actual = Array.isArray(slots) ? slots.length : 0;
  const allOnRequestedDate = Array.isArray(slots) && slots.every((slot) =>
    slot?.start && localDateInZone(slot.start, timeZone) === localDate);
  return {
    localDate,
    timeZone,
    expectedSlotCount: expected,
    actualSlotCount: actual,
    complete: actual === expected && allOnRequestedDate,
    allOnRequestedDate,
  };
}
