# Planner

<div class="planner-minimal" data-planner-url="https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow.json" data-planner-title="Homey Planner">
  <h2 class="pm-planner-title">Homey Planner</h2>
  <div class="pm-status">Plannerdata laden…</div>
  <div class="pm-content" hidden>
    <section class="pm-section">
      <h2>24-uurs forecast</h2>
      <p class="pm-note">Base load, PV en verwachte import/export. Positief = import; negatief = export.</p>
      <div class="pm-legend">
        <span><i class="pm-key base"></i>Base load</span>
        <span><i class="pm-key pv"></i>PV</span>
        <span><i class="pm-key net"></i>Verwachte import/export</span>
      </div>

      <div class="pm-aligned-row pm-forecast-row">
        <div class="pm-label-gutter" aria-hidden="true"></div>
        <div class="pm-forecast-frame">
          <div class="pm-quarter-grid pm-balance-grid pm-forecast" aria-label="24-uurs forecastgrafiek"></div>
        </div>
      </div>
      <div class="pm-aligned-row pm-axis-row" aria-hidden="true">
        <div class="pm-label-gutter"></div>
        <div class="pm-quarter-grid pm-time-axis"></div>
      </div>
    </section>

    <section class="pm-section">
      <h2>Geplande tijdsvakken</h2>
      <div class="pm-deadline" hidden></div>
      <div class="pm-slots"></div>
    </section>
  </div>
</div>

<div class="planner-minimal" data-planner-url="https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow-pi.json" data-planner-title="Pi Planner (shadow)">
  <h2 class="pm-planner-title">Pi Planner (shadow)</h2>
  <div class="pm-status">Plannerdata laden…</div>
  <div class="pm-content" hidden>
    <section class="pm-section">
      <h2>24-uurs forecast</h2>
      <p class="pm-note">Base load, PV en verwachte import/export. Positief = import; negatief = export.</p>
      <div class="pm-legend">
        <span><i class="pm-key base"></i>Base load</span>
        <span><i class="pm-key pv"></i>PV</span>
        <span><i class="pm-key net"></i>Verwachte import/export</span>
      </div>
      <div class="pm-aligned-row pm-forecast-row">
        <div class="pm-label-gutter" aria-hidden="true"></div>
        <div class="pm-forecast-frame">
          <div class="pm-quarter-grid pm-balance-grid pm-forecast" aria-label="24-uurs forecastgrafiek"></div>
        </div>
      </div>
      <div class="pm-aligned-row pm-axis-row" aria-hidden="true">
        <div class="pm-label-gutter"></div>
        <div class="pm-quarter-grid pm-time-axis"></div>
      </div>
    </section>

    <section class="pm-section">
      <h2>Geplande tijdsvakken</h2>
      <div class="pm-deadline" hidden></div>
      <div class="pm-slots"></div>
    </section>
  </div>
</div>

<style>
  .planner-minimal{--pm-label-col:64px;--pm-col-gap:.4rem;--pm-slot-gap:1px;max-width:1200px;margin:0 auto}
  .pm-status{padding:1rem 0;color:var(--md-default-fg-color--light)}
  .pm-status.pm-error{color:var(--md-typeset-color)}
  .pm-section{margin:1.1rem 0 1.5rem}
  .pm-section h2{font-size:.9rem;margin:0 0 .3rem}
  .pm-note{margin:.15rem 0 .45rem;color:var(--md-default-fg-color--light);font-size:.7rem}
  .pm-legend{display:flex;flex-wrap:wrap;gap:.35rem .7rem;margin-bottom:.4rem}
  .pm-legend span{font-size:.64rem;display:inline-flex;align-items:center;gap:.25rem}
  .pm-key{display:inline-block;width:.62rem;height:.62rem;border-radius:2px}
  .pm-key.base,.pm-bar.base{background:#6e7f90}
  .pm-key.pv,.pm-bar.pv{background:#d7a900}
  .pm-key.net,.pm-bar.net.import{background:#3277b3}
  .pm-bar.net.export{background:#2e9b67}

  /* Eén gedeelde geometrie voor forecast, tijdas en device-tracks. */
  .pm-aligned-row,.pm-row{display:grid;grid-template-columns:var(--pm-label-col) minmax(0,1fr);gap:var(--pm-col-gap);min-width:0}
  .pm-quarter-grid{display:grid;grid-template-columns:repeat(96,minmax(0,1fr));gap:var(--pm-slot-gap);min-width:0}

  .pm-forecast-frame{height:165px;border:1px solid var(--md-default-fg-color--lightest);border-radius:.45rem;overflow:hidden;background:color-mix(in srgb,var(--md-default-bg-color) 96%,var(--md-default-fg-color) 4%)}
  .pm-balance-grid{height:100%;padding:.35rem .2rem .2rem;box-sizing:border-box}
  .pm-balance-col{position:relative;min-width:0;height:100%}
  .pm-zero{position:absolute;left:0;right:0;top:50%;border-top:1px solid var(--md-default-fg-color--lightest)}
  .pm-bar{position:absolute;width:26%;min-height:2px}
  .pm-bar.base{left:4%;border-radius:2px 2px 0 0}
  .pm-bar.pv{left:36%;border-radius:2px 2px 0 0}
  .pm-bar.net{left:68%}
  .pm-bar.net.import{border-radius:2px 2px 0 0}
  .pm-bar.net.export{border-radius:0 0 2px 2px}

  .pm-axis-row{margin-top:.25rem}
  .pm-time-axis{padding:0 .2rem;box-sizing:border-box;min-height:14px}
  .pm-time{font-size:.48rem;opacity:.7;white-space:nowrap;transform:translateX(-1px)}

  .pm-deadline{margin:.15rem 0 .45rem calc(var(--pm-label-col) + var(--pm-col-gap));padding:.38rem .55rem;border:1px solid var(--md-default-fg-color--lightest);border-radius:.35rem;font-size:.65rem;font-weight:600}
  .pm-slots{display:grid;gap:.22rem}
  .pm-row{align-items:center}
  .pm-row-label{font-size:.62rem;font-weight:700;opacity:.78;text-align:right}
  .pm-track-frame{height:24px;border-bottom:1px solid var(--md-default-fg-color--lightest);min-width:0}
  .pm-track{height:100%;padding:0 .2rem;box-sizing:border-box;align-items:center}
  .pm-segment{height:18px;border-radius:.25rem;min-width:2px;align-self:center}
  .pm-segment.tesla{background:#8f4ac7}
  .pm-segment.boiler{background:#2aa9b8}
  .pm-segment.battery{background:#66aa45}
  .pm-empty{grid-column:1 / -1;font-size:.62rem;opacity:.65;line-height:24px}

  @media(prefers-color-scheme:dark){.pm-key.base,.pm-bar.base{background:#98a8b7}.pm-key.pv,.pm-bar.pv{background:#e4bd35}.pm-key.net,.pm-bar.net.import{background:#69a4d7}.pm-bar.net.export{background:#54b889}}
  @media(max-width:600px){.planner-minimal{--pm-label-col:54px}.pm-forecast-frame{height:150px}.pm-row-label{font-size:.56rem}}
</style>

<script>
(() => {
  const finite = v => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
  const unwrap = payload => payload?.plan?.plan?.actions ? payload.plan : (payload?.plan || payload || {});
  const hhmm = iso => {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '—' : d.toLocaleTimeString('nl-NL', {hour:'2-digit', minute:'2-digit'});
  };

  function initPlanner(ROOT) {
    if (!ROOT || ROOT.dataset.initialized === '1') return;
    ROOT.dataset.initialized = '1';

    const DATA_URL = ROOT.dataset.plannerUrl;
    const status = ROOT.querySelector('.pm-status');
    const content = ROOT.querySelector('.pm-content');
    const forecast = ROOT.querySelector('.pm-forecast');
    const timeAxis = ROOT.querySelector('.pm-time-axis');
    const deadlineEl = ROOT.querySelector('.pm-deadline');
    const slotsEl = ROOT.querySelector('.pm-slots');

    function renderDeadline(p) {
      const t = p?.inputs?.tesla || {};
      const active = t.deadlineActive === true;
      if (!active) {
        deadlineEl.hidden = true;
        deadlineEl.textContent = '';
        return;
      }
      const parts = [`Tesla deadline actief · ${hhmm(t.deadlineAt)}`];
      if (finite(t.maxA)) parts.push(`max ${Math.round(Number(t.maxA))} A`);
      if (finite(t.requiredDeadlineSlots)) parts.push(`${Math.round(Number(t.requiredDeadlineSlots))} slots nodig`);
      if (finite(t.remainingKWh)) parts.push(`${Number(t.remainingKWh).toFixed(2).replace('.', ',')} kWh resterend`);
      deadlineEl.textContent = parts.join(' · ');
      deadlineEl.hidden = false;
    }

    function renderForecast(actions) {
      forecast.replaceChildren();
      timeAxis.replaceChildren();

      const values = [];
      actions.forEach(a => {
        ['baseLoadForecastW','pvForecastW','netBeforeFlexW'].forEach(k => {
          if (finite(a[k])) values.push(Math.abs(Number(a[k])));
        });
      });

      const max = Math.max(1000, ...values);

      actions.forEach((a, idx) => {
        const col = document.createElement('div');
        col.className = 'pm-balance-col';
        col.style.gridColumn = `${idx+1}`;

        const zero = document.createElement('div');
        zero.className = 'pm-zero';
        col.append(zero);

        const addBar = (kind, v) => {
          if (!finite(v)) return;
          const n = Number(v);
          const h = Math.max(2, Math.min(48, Math.abs(n) / max * 48));

          const b = document.createElement('div');
          b.className = `pm-bar ${kind}`;
          b.style.height = `${h}%`;

          if (kind === 'net') {
            b.classList.add(n < 0 ? 'export' : 'import');
            b.style.bottom = n < 0 ? `${50-h}%` : '50%';
          } else {
            b.style.bottom = '50%';
          }

          b.title = `${hhmm(a.start)} · ${kind==='base'?'Base load':kind==='pv'?'PV':'Verwachte import/export'} ${Math.round(n)} W`;
          col.append(b);
        };

        addBar('base', a.baseLoadForecastW);
        addBar('pv', a.pvForecastW);
        addBar('net', a.netBeforeFlexW);

        forecast.append(col);

        if (idx % 12 === 0) {
          const t = document.createElement('span');
          t.className = 'pm-time';
          t.style.gridColumn = `${idx+1} / span 12`;
          t.textContent = hhmm(a.start);
          timeAxis.append(t);
        }
      });
    }

    function actionActive(asset, a) {
      const raw = String(a?.[asset] ?? 'HOLD').toUpperCase();
      return !(raw === 'HOLD' || raw === 'NONE' || raw === 'OFF' || raw === '0' || raw === '');
    }

    function addRow(label, asset, cssClass, actions) {
      const row = document.createElement('div');
      row.className = 'pm-row';

      const name = document.createElement('div');
      name.className = 'pm-row-label';
      name.textContent = label;

      const frame = document.createElement('div');
      frame.className = 'pm-track-frame';

      const track = document.createElement('div');
      track.className = 'pm-quarter-grid pm-track';

      frame.append(track);
      row.append(name, frame);

      let start = null;

      const flush = end => {
        if (start === null) return;

        const seg = document.createElement('div');
        seg.className = `pm-segment ${cssClass}`;
        seg.style.gridColumn = `${start+1} / ${end+1}`;

        const first = actions[start];
        const last = actions[end-1];

        seg.title = `${label}: ${hhmm(first.start)}–${hhmm(last.end || new Date(new Date(last.start).getTime()+15*60000).toISOString())}`;
        track.append(seg);
      };

      for (let i = 0; i <= actions.length; i++) {
        const active = i < actions.length && actionActive(asset, actions[i]);
        if (active && start === null) start = i;
        if (!active && start !== null) {
          flush(i);
          start = null;
        }
      }

      if (!track.children.length) {
        const e = document.createElement('div');
        e.className = 'pm-empty';
        e.textContent = 'geen tijdsvakken';
        track.append(e);
      }

      slotsEl.append(row);
    }

    async function load() {
      try {
        const r = await fetch(`${DATA_URL}?ts=${Date.now()}`, {cache:'no-store'});
        if (!r.ok) throw new Error(`HTTP ${r.status}`);

        const payload = await r.json();
        const p = unwrap(payload);
        const actions = Array.isArray(p?.plan?.actions) ? p.plan.actions : [];

        if (actions.length !== 96) {
          throw new Error(`verwacht 96 kwartierslots, ontvangen ${actions.length}`);
        }

        renderDeadline(p);
        renderForecast(actions);

        slotsEl.replaceChildren();
        addRow('Tesla', 'tesla', 'tesla', actions);
        addRow('Boiler', 'warmWater', 'boiler', actions);

        if (actions.some(a => actionActive('battery', a))) {
          addRow('Accu', 'battery', 'battery', actions);
        }

        status.remove();
        content.hidden = false;

      } catch (e) {
        status.className = 'pm-status pm-error';
        status.textContent = `Plannerdata laden mislukt: ${e.message}`;
      }
    }

    load();
  }

  document.querySelectorAll('.planner-minimal').forEach(initPlanner);
})();
</script>
