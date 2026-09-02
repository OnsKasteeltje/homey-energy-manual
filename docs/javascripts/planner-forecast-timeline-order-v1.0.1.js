(() => {
  const ROOT_ID = 'planner-shadow';
  const MOVED_ID = 'ps-forecast-load-windows';

  function sectionByTitle(root, title) {
    return [...root.querySelectorAll(':scope > section.ps-section')]
      .find(section => section.querySelector(':scope > h2')?.textContent.trim() === title) || null;
  }

  function findPvForecastCard(kpis) {
    return [...kpis.children].find(card =>
      card.querySelector('.ps-card-title')?.textContent.trim() === 'PV forecast'
    ) || null;
  }

  function moveForecastRows() {
    const root = document.getElementById(ROOT_ID);
    if (!root) return;

    const priceSection = sectionByTitle(root, 'Prijs & planneracties');
    const kpis = root.querySelector(':scope > .ps-kpi-grid');
    if (!priceSection || !kpis) return;

    const pvCard = findPvForecastCard(kpis);
    if (!pvCard) return;

    const actionRows = [...priceSection.querySelectorAll(':scope > .ps-action-row')];
    let forecastSection = document.getElementById(MOVED_ID);

    if (!forecastSection && !actionRows.length) return;

    if (!forecastSection) {
      forecastSection = document.createElement('section');
      forecastSection.id = MOVED_ID;
      forecastSection.className = 'ps-section ps-forecast-load-windows';
      forecastSection.style.gridColumn = '1 / -1';

      const heading = document.createElement('h2');
      heading.textContent = 'Planner forecast laadtijdvakken';

      const note = document.createElement('div');
      note.className = 'ps-chart-note';
      note.textContent = 'Geplande flexibele lasten direct onder PV forecast, op dezelfde 96 kwartierslots als de overige Planner-tijdlijnen.';

      forecastSection.append(heading, note);
    }

    // Exact requested hierarchy: Base load + PV forecast, then forecast load windows,
    // then the remaining KPI cards. The section spans the complete KPI grid width.
    if (forecastSection.parentElement !== kpis || forecastSection.previousElementSibling !== pvCard) {
      pvCard.after(forecastSection);
    }

    actionRows.forEach(row => forecastSection.append(row));
  }

  function install() {
    moveForecastRows();
    const root = document.getElementById(ROOT_ID);
    if (!root || root.dataset.forecastTimelineOrderObserver === '1') return;
    root.dataset.forecastTimelineOrderObserver = '1';
    const observer = new MutationObserver(() => moveForecastRows());
    observer.observe(root, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }

  if (window.document$?.subscribe) window.document$.subscribe(install);
})();
