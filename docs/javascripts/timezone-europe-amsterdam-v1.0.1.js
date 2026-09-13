(() => {
  'use strict';

  const TZ = 'Europe/Amsterdam';
  const BASE = '/homey-energy-manual/';
  const READY_ATTR = 'data-tz-ready';

  // Prevent a raw UTC datetime-local value from flashing before the canonical
  // Europe/Amsterdam conversion has been applied.
  const style = document.createElement('style');
  style.textContent = `.tesla-inline-deadline:not([${READY_ATTR}="true"]){visibility:hidden}`;
  document.head.appendChild(style);

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
    if (!input) return;

    // Never overwrite a deadline that the user is actively editing.
    if (document.activeElement === input) {
      input.setAttribute(READY_ATTR, 'true');
      return;
    }

    const core = await getJson('data/energy-state-v2.json');
    const t = core?.tesla || {};

    if (t.deadline_active === true && t.deadline_at) {
      const local = localMinute(t.deadline_at);
      if (!local) return; // fail closed: do not reveal an unverified raw value
      input.value = local;
    }

    input.setAttribute(READY_ATTR, 'true');
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
    void fixTeslaDeadlineInput();
    void fixPlanner();
  }

  // The timezone guard is loaded before the frontend bundle. Observe the DOM so
  // dynamically-created deadline inputs are corrected before they become visible.
  const observer = new MutationObserver(() => {
    const input = document.querySelector('.tesla-inline-deadline');
    if (input && input.getAttribute(READY_ATTR) !== 'true') void fixTeslaDeadlineInput();
  });
  observer.observe(document.documentElement, {subtree: true, childList: true});

  document.addEventListener('DOMContentLoaded', run);
  document.addEventListener('liveenergyrendered', run);
  document.addEventListener('energycorev2state', run);
  document.addEventListener('appdatarefresh', run);
  if (document.readyState !== 'loading') run();
  if (window.document$?.subscribe) window.document$.subscribe(run);
})();
