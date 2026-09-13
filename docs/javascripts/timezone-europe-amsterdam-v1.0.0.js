(() => {
  'use strict';

  const TZ = 'Europe/Amsterdam';
  const BASE = '/homey-energy-manual/';

  const localParts = value => {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return null;
    return Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
      timeZone: TZ,
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
    }).formatToParts(d).filter(x => x.type !== 'literal').map(x => [x.type, x.value]));
  };

  const localMinute = value => {
    const p = localParts(value);
    return p ? `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}` : '';
  };

  const localDateTimeLabel = value => {
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? '—' : new Intl.DateTimeFormat('nl-NL', {
      timeZone: TZ,
      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
    }).format(d);
  };

  const localTimeLabel = value => {
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? '—' : new Intl.DateTimeFormat('nl-NL', {
      timeZone: TZ,
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
    }).format(d);
  };

  async function getJson(path) {
    try {
      const r = await fetch(`${BASE}${path}?tzfix=${Date.now()}`, {cache: 'no-store'});
      return r.ok ? await r.json() : null;
    } catch (_) {
      return null;
    }
  }

  async function fixTeslaDeadlineInput() {
    const input = document.querySelector('.tesla-inline-deadline');
    if (!input || document.activeElement === input) return;
    const core = await getJson('data/energy-state-v2.json');
    const t = core?.tesla || {};
    if (t.deadline_active === true && t.deadline_at) {
      const local = localMinute(t.deadline_at);
      if (local && input.value !== local) input.value = local;
    }
  }

  async function fixPlanner() {
    for (const root of document.querySelectorAll('.planner-minimal')) {
      const url = root.dataset.url || root.dataset.plannerUrl;
      if (!url) continue;
      try {
        const r = await fetch(`${url}${url.includes('?') ? '&' : '?'}tzfix=${Date.now()}`, {cache: 'no-store'});
        if (!r.ok) continue;
        const payload = await r.json();
        const p = payload?.plan?.plan?.actions ? payload.plan : (payload?.plan || payload || {});
        const actions = Array.isArray(p?.plan?.actions) ? p.plan.actions : [];
        const dp = p?.deadlinePlan || {};

        const deadline = root.querySelector('.pm-deadline');
        if (deadline && dp.active === true && dp.deadlineAt) {
          const remaining = Number.isFinite(Number(dp.remainingKWh)) ? Number(dp.remainingKWh).toFixed(2) : '—';
          deadline.textContent = `Tesla deadline actief · ${localDateTimeLabel(dp.deadlineAt)} · resterend ${remaining} kWh`;
          deadline.hidden = false;
        }

        const axis = root.querySelector('.pm-time-axis');
        if (axis && actions.length) {
          const labels = axis.querySelectorAll('.pm-time');
          const start = new Date(actions[0].start).getTime();
          labels.forEach((label, i) => {
            label.textContent = localTimeLabel(new Date(start + i * 12 * 15 * 60 * 1000).toISOString());
          });
        }
      } catch (_) {}
    }
  }

  function run() {
    setTimeout(fixTeslaDeadlineInput, 0);
    setTimeout(fixPlanner, 0);
  }

  document.addEventListener('DOMContentLoaded', run);
  document.addEventListener('liveenergyrendered', run);
  document.addEventListener('energycorev2state', run);
  document.addEventListener('appdatarefresh', run);
  if (document.readyState !== 'loading') run();
  if (window.document$?.subscribe) window.document$.subscribe(run);
})();
