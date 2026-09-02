(() => {
  const ROOT_ID = 'planner-shadow';
  const MOVED_ID = 'ps-forecast-load-windows';

  function sectionByTitle(root, title) {
    return [...root.querySelectorAll(':scope > section.ps-section')]
      .find(section => section.querySelector(':scope > h2')?.textContent.trim() === title) || null;
  }

  function findPvForecastSection(root) {
    return [...root.querySelectorAll(':scope > section.ps-section')]
      .find(section => section.querySelector(':scope > h2')?.textContent.trim() === 'PV forecast') || null;
  }

  function moveForecastRows() {
    const root = document.getElementById(ROOT_ID);
    if (!root) return;

    const priceSection = sectionByTitle(root, 'Prijs & planneracties');
    const pvForecastSection = findPvForecastSection(root);
    if (!priceSection || !pvForecastSection) return;

    const actionRows = [...priceSection.querySelectorAll(':scope > .ps-action-row')];
    let forecastSection = document.getElementById(MOVED_ID);
    if (!forecastSection && !actionRows.length) return;

    if (!forecastSection) {
      forecastSection = document.createElement('section');
      forecastSection.id = MOVED_ID;
      forecastSection.className = 'ps-section ps-forecast-load-windows';

      const heading = document.createElement('h2');
      heading.textContent = 'Planner forecast laadtijdvakken';

      const note = document.createElement('div');
      note.className = 'ps-chart-note';
      note.textContent = 'Geplande flexibele lasten op dezelfde 96 kwartierslots als de PV forecast.';
      forecastSection.append(heading, note);
    }

    // Literal requested hierarchy: the complete PV forecast graph section first,
    // then immediately the planner load-window timelines. No KPI-card anchoring.
    if (forecastSection.parentElement !== root || forecastSection.previousElementSibling !== pvForecastSection) {
      pvForecastSection.after(forecastSection);
    }

    actionRows.forEach(row => forecastSection.append(row));
  }

  function install() {
    moveForecastRows();
    const root = document.getElementById(ROOT_ID);
    if (!root || root.dataset.forecastTimelineOrderObserver === '2') return;
    root.dataset.forecastTimelineOrderObserver = '2';
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
