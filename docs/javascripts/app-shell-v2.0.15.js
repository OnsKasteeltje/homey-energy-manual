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

  if ('ontouchstart' in window) {
    let y = 0;
    window.addEventListener('touchstart', e => { if (window.scrollY === 0) y = e.touches[0].clientY; else y = 0; }, { passive: true });
    window.addEventListener('touchend', e => {
      if (!y) return;
      const dy = e.changedTouches[0].clientY - y;
      y = 0;
      if (dy > 110 && window.scrollY === 0) location.reload();
    }, { passive: true });
  }
})();
