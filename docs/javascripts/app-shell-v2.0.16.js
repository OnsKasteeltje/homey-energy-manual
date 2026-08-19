(() => {
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  document.documentElement.classList.toggle('home-energy-app', isStandalone);

  const items = [
    { href: '/', label: 'Home', icon: '⌂' },
    { href: '/live-energie/', label: 'Live', icon: '↯' },
    { href: '/energiehistorie/', label: 'Historie', icon: '▥' },
    { href: '/groepen-fasen/', label: 'Groepen', icon: '▦' },
    { href: '/flows/', label: 'Flows', icon: '◇' }
  ];

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

  function refreshData() {
    document.dispatchEvent(new Event('DOMContentSwitch'));
  }

  function render() {
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

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', render, { once: true });
  else render();

  let lastVisibleRefresh = 0;
  const refreshOnReturn = () => {
    if (document.hidden) return;
    const now = Date.now();
    if (now - lastVisibleRefresh < 15000) return;
    lastVisibleRefresh = now;
    refreshData();
  };
  document.addEventListener('visibilitychange', refreshOnReturn);
  window.addEventListener('pageshow', refreshOnReturn);
  window.addEventListener('focus', refreshOnReturn);
  window.addEventListener('online', refreshOnReturn);

  if ('ontouchstart' in window) {
    let startY = null;
    let maxDy = 0;
    const atTop = () => (document.scrollingElement?.scrollTop || window.scrollY || 0) <= 2;
    window.addEventListener('touchstart', e => {
      startY = atTop() && e.touches[0] ? e.touches[0].clientY : null;
      maxDy = 0;
    }, { passive: true });
    window.addEventListener('touchmove', e => {
      if (startY === null || !e.touches[0]) return;
      maxDy = Math.max(maxDy, e.touches[0].clientY - startY);
    }, { passive: true });
    window.addEventListener('touchend', () => {
      const shouldRefresh = startY !== null && maxDy > 70;
      startY = null;
      maxDy = 0;
      if (shouldRefresh) refreshData();
    }, { passive: true });
  }
})();
