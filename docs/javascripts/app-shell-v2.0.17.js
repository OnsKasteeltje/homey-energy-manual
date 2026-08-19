(() => {
  'use strict';
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  document.documentElement.classList.toggle('home-energy-app', isStandalone);

  const REFRESH_MS = 5 * 60 * 1000;
  const MIN_REFRESH_GAP_MS = 15000;
  const items = [
    { href: '/', label: 'Home', icon: '⌂' },
    { href: '/live-energie/', label: 'Live', icon: '↯' },
    { href: '/energiehistorie/', label: 'Historie', icon: '▥' },
    { href: '/groepen-fasen/', label: 'Groepen', icon: '▦' },
    { href: '/flows/', label: 'Flows', icon: '◇' }
  ];

  const fmtAge = ms => {
    if (!Number.isFinite(ms) || ms < 0) return 'onbekend';
    const min = Math.round(ms / 60000);
    if (min < 1) return 'zojuist';
    if (min < 60) return `${min} min geleden`;
    const h = Math.floor(min / 60), m = min % 60;
    return m ? `${h} u ${m} min geleden` : `${h} u geleden`;
  };
  const severity = ms => !Number.isFinite(ms) || ms > 30*60*1000 ? 'error' : ms > 15*60*1000 ? 'warn' : 'ok';

  function basePath() {
    const marker = '/homey-energy-manual/';
    return location.pathname.includes(marker) ? marker : '/';
  }
  function route(href) {
    const base = basePath();
    if (href === '/') return base;
    return `${base.replace(/\/$/, '')}${href}`;
  }
  function normalized(path) {
    return path.replace(/index\.html$/, '').replace(/\/$/, '') || '/';
  }

  function renderNav() {
    if (document.querySelector('.home-energy-bottom-nav')) return;
    const nav = document.createElement('nav');
    nav.className = 'home-energy-bottom-nav';
    nav.setAttribute('aria-label', 'App navigatie');
    const current = normalized(location.pathname);
    nav.innerHTML = items.map(item => {
      const target = route(item.href);
      const targetNorm = normalized(new URL(target, location.origin).pathname);
      const active = item.href === '/' ? current === targetNorm : current.startsWith(targetNorm);
      return `<a href="${target}" class="${active ? 'is-active' : ''}" ${active ? 'aria-current="page"' : ''}><span class="app-nav-icon" aria-hidden="true">${item.icon}</span><span>${item.label}</span></a>`;
    }).join('');
    document.body.appendChild(nav);
  }

  function shouldShowFreshness() {
    return !!(document.getElementById('home-architecture') || document.getElementById('live-energy-flow'));
  }
  function ensureFreshness() {
    if (!shouldShowFreshness()) return null;
    let el = document.getElementById('app-feed-freshness');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'app-feed-freshness';
    el.className = 'app-feed-freshness app-feed-freshness-unknown';
    el.setAttribute('role', 'status');
    const target = document.querySelector('.md-content__inner') || document.querySelector('main');
    if (target) target.insertBefore(el, target.firstChild);
    return el;
  }
  function renderFreshness() {
    const el = ensureFreshness(); if (!el) return;
    const raw = window.EnergyCoreV2?.state?.raw;
    const generated = Date.parse(raw?.meta?.generated_at || '');
    const source = Date.parse(raw?.meta?.source_sample_at || '');
    const feedAge = Number.isFinite(generated) ? Date.now() - generated : NaN;
    const sourceAge = Number.isFinite(source) ? Date.now() - source : NaN;
    const worst = Math.max(Number.isFinite(feedAge) ? feedAge : Infinity, Number.isFinite(sourceAge) ? sourceAge : 0);
    const level = severity(worst);
    el.className = `app-feed-freshness app-feed-freshness-${level}`;
    const label = level === 'ok' ? 'Actueel' : level === 'warn' ? 'Vertraagd' : 'Data verouderd';
    el.textContent = `${label} · publicatie ${fmtAge(feedAge)}${Number.isFinite(sourceAge) ? ` · bron ${fmtAge(sourceAge)}` : ''}`;
    el.title = 'App-data wordt bij openen, terugkeren, opnieuw online komen en iedere 5 minuten opnieuw opgehaald. Waarschuwing >15 min; fout >30 min.';
  }

  let lastRefresh = 0;
  async function refreshData(reason='manual', force=false) {
    if (document.hidden && reason !== 'manual') return false;
    const now = Date.now();
    if (!force && now - lastRefresh < MIN_REFRESH_GAP_MS) return false;
    lastRefresh = now;
    document.documentElement.classList.add('app-data-refreshing');
    try {
      // DOMContentSwitch is the shared refresh contract: active components perform cache:no-store fetches.
      document.dispatchEvent(new CustomEvent('DOMContentSwitch', { detail: { reason, at: new Date(now).toISOString() } }));
      document.dispatchEvent(new CustomEvent('appdatarefresh', { detail: { reason, at: new Date(now).toISOString() } }));
      // Give component fetches time to settle before freshness is repainted.
      setTimeout(renderFreshness, 800);
      return true;
    } finally {
      setTimeout(() => document.documentElement.classList.remove('app-data-refreshing'), 900);
    }
  }

  window.HomeEnergyApp = { version: '2.0.17', refreshData, renderFreshness };

  function boot() {
    renderNav();
    renderFreshness();
    refreshData('boot', true);
    setInterval(() => refreshData('interval'), REFRESH_MS);
    setInterval(renderFreshness, 60000);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();

  const onReturn = reason => { if (!document.hidden) refreshData(reason); };
  document.addEventListener('visibilitychange', () => onReturn('visibility'));
  window.addEventListener('pageshow', () => onReturn('pageshow'));
  window.addEventListener('focus', () => onReturn('focus'));
  window.addEventListener('online', () => onReturn('online'));
  document.addEventListener('energycorev2state', renderFreshness);

  if ('ontouchstart' in window) {
    let startY = null, maxDy = 0;
    const atTop = () => (document.scrollingElement?.scrollTop || window.scrollY || 0) <= 2;
    window.addEventListener('touchstart', e => { startY = atTop() && e.touches[0] ? e.touches[0].clientY : null; maxDy = 0; }, { passive: true });
    window.addEventListener('touchmove', e => { if (startY !== null && e.touches[0]) maxDy = Math.max(maxDy, e.touches[0].clientY - startY); }, { passive: true });
    window.addEventListener('touchend', () => {
      const doRefresh = startY !== null && maxDy > 70;
      startY = null; maxDy = 0;
      if (doRefresh) refreshData('pull-to-refresh', true);
    }, { passive: true });
  }
})();
