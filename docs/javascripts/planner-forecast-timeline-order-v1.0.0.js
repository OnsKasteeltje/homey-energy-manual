(() => {
  const ROOT_ID = 'planner-shadow';
  const MOVED_ID = 'ps-forecast-load-windows';

  function sectionByTitle(root, title) {
    return [...root.querySelectorAll(':scope > section.ps-section')]
      .find(section => section.querySelector(':scope > h2')?.textContent.trim() === title) || null;
  }

  function moveForecastRows() {
    const root = document.getElementById(ROOT_ID);
    if (!root) return;

    const priceSection = sectionByTitle(root, 'Prijs & planneracties');
    const balanceSection = sectionByTitle(root, '24-uurs energiebalans');
    if (!priceSection || !balanceSection) return;

    const actionRows = [...priceSection.querySelectorAll(':scope > .ps-action-row')];
    if (!actionRows.length) return;

    let forecastSection = document.getElementById(MOVED_ID);
    if (!forecastSection) {
      forecastSection = document.createElement('section');
      forecastSection.id = MOVED_ID;
      forecastSection.className = 'ps-section ps-forecast-load-windows';

      const heading = document.createElement('h2');
      heading.textContent = 'Planner forecast laadtijdvakken';

      const note = document.createElement('div');
      note.className = 'ps-chart-note';
      note.textContent = 'Geplande flexibele lasten op dezelfde 96 kwartierslots als PV-forecast en energiebalans.';

      forecastSection.append(heading, note);
      balanceSection.before(forecastSection);
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
