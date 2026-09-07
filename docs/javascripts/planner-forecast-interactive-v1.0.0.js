(() => {
  'use strict';

  const SELECTOR = '.planner-minimal';
  const SLOT_MS = 15 * 60 * 1000;
  const NS = 'http://www.w3.org/2000/svg';

  const finite = v => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
  const unwrap = payload => payload?.plan?.plan?.actions ? payload.plan : (payload?.plan || payload || {});
  const kw = v => finite(v) ? `${(Number(v) / 1000).toLocaleString('nl-NL', {minimumFractionDigits:2, maximumFractionDigits:2})} kW` : '—';
  const hhmm = iso => {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '—' : d.toLocaleTimeString('nl-NL', {hour:'2-digit', minute:'2-digit'});
  };
  const fullTime = iso => {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('nl-NL', {
      weekday:'short', day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit'
    });
  };
  const svgEl = (name, attrs = {}) => {
    const n = document.createElementNS(NS, name);
    Object.entries(attrs).forEach(([k,v]) => n.setAttribute(k, String(v)));
    return n;
  };

  function installStyles() {
    if (document.getElementById('pm-interactive-chart-style')) return;
    const style = document.createElement('style');
    style.id = 'pm-interactive-chart-style';
    style.textContent = `
      .pm-forecast-frame{position:relative;overflow:hidden}
      .pm-forecast.pm-interactive-chart{display:block!important;position:relative;height:100%;padding:0!important;touch-action:pan-y;background:transparent}
      .pm-interactive-chart svg{display:block;width:100%;height:100%;overflow:visible}
      .pm-ref-line{stroke:color-mix(in srgb,var(--md-default-fg-color) 17%,transparent);stroke-width:.8;stroke-dasharray:4 4;vector-effect:non-scaling-stroke}
      .pm-zero-line{stroke:color-mix(in srgb,var(--md-default-fg-color) 30%,transparent);stroke-width:1;vector-effect:non-scaling-stroke}
      .pm-pv-bar{fill:#d7a900;opacity:.9}
      .pm-import-bar{fill:#3277b3;opacity:.82}
      .pm-export-bar{fill:#2e9b67;opacity:.85}
      .pm-base-area{fill:#6e7f90;opacity:.13}
      .pm-base-line{fill:none;stroke:#6e7f90;stroke-width:2.1;stroke-linejoin:round;stroke-linecap:round;vector-effect:non-scaling-stroke}
      .pm-crosshair{position:absolute;top:0;bottom:0;width:1px;background:color-mix(in srgb,#3277b3 75%,var(--md-default-fg-color));pointer-events:none;z-index:4;display:none}
      .pm-crosshair::after{content:'';position:absolute;top:50%;left:50%;width:7px;height:7px;border-radius:50%;background:var(--md-default-bg-color);border:2px solid #3277b3;transform:translate(-50%,-50%)}
      .pm-hover-tooltip{position:absolute;z-index:6;min-width:190px;max-width:230px;padding:.48rem .58rem;border-radius:.45rem;background:color-mix(in srgb,var(--md-default-bg-color) 96%,var(--md-default-fg-color) 4%);border:1px solid var(--md-default-fg-color--lightest);box-shadow:0 6px 20px rgba(0,0,0,.16);font-size:.58rem;line-height:1.45;pointer-events:none;display:none}
      .pm-hover-tooltip strong{display:block;margin-bottom:.24rem;font-size:.62rem}
      .pm-hover-row{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:.25rem .35rem;white-space:nowrap}
      .pm-hover-dot{width:.48rem;height:.48rem;border-radius:2px}
      .pm-hover-dot.base{background:#6e7f90}.pm-hover-dot.pv{background:#d7a900}.pm-hover-dot.import{background:#3277b3}.pm-hover-dot.export{background:#2e9b67}
      .pm-hover-net{margin-top:.28rem;padding-top:.28rem;border-top:1px solid var(--md-default-fg-color--lightest);font-weight:700}
      .pm-scale-hint{position:absolute;right:.35rem;top:.25rem;font-size:.45rem;opacity:.55;pointer-events:none;z-index:2}
      .pm-legend .pm-key.import{background:#3277b3}.pm-legend .pm-key.export{background:#2e9b67}
      @media(prefers-color-scheme:dark){.pm-pv-bar{fill:#e4bd35}.pm-import-bar{fill:#69a4d7}.pm-export-bar{fill:#54b889}.pm-base-line{stroke:#98a8b7}.pm-base-area{fill:#98a8b7}.pm-hover-dot.base{background:#98a8b7}.pm-hover-dot.pv{background:#e4bd35}.pm-hover-dot.import{background:#69a4d7}.pm-hover-dot.export{background:#54b889}}
      @media(max-width:600px){.pm-hover-tooltip{min-width:165px;max-width:195px;font-size:.54rem;padding:.42rem .48rem}.pm-hover-tooltip strong{font-size:.58rem}}
    `;
    document.head.append(style);
  }

  function normalizeActions(payload) {
    const p = unwrap(payload);
    const actions = Array.isArray(p?.plan?.actions) ? p.plan.actions : [];
    return actions.slice(0, 96);
  }

  function updateLegend(root) {
    const legend = root.querySelector('.pm-legend');
    if (!legend) return;
    legend.replaceChildren();
    [
      ['base','Base load (forecast)'],
      ['pv','PV (forecast)'],
      ['import','Verwachte import'],
      ['export','Verwachte export']
    ].forEach(([kind,label]) => {
      const span = document.createElement('span');
      const key = document.createElement('i');
      key.className = `pm-key ${kind}`;
      span.append(key, document.createTextNode(label));
      legend.append(span);
    });
    const note = root.querySelector('.pm-note');
    if (note) note.textContent = 'Base load, PV en verwachte import/export. Positief = import; negatief = export. Hover of tik op een kwartier voor details.';
  }

  function renderAxis(root, actions) {
    const axis = root.querySelector('.pm-time-axis');
    if (!axis || !actions.length) return;
    axis.replaceChildren();
    axis.style.gridTemplateColumns = 'repeat(96,minmax(0,1fr))';
    const start = new Date(actions[0].start).getTime();
    for (let idx=0; idx<96; idx+=12) {
      const t = document.createElement('span');
      t.className = 'pm-time';
      t.style.gridColumn = `${idx+1} / span 12`;
      t.textContent = hhmm(new Date(start + idx*SLOT_MS).toISOString());
      axis.append(t);
    }
  }

  function derive(a) {
    const base = finite(a?.baseLoadForecastW) ? Number(a.baseLoadForecastW) : 0;
    const pv = finite(a?.pvForecastW) ? Math.max(0, Number(a.pvForecastW)) : 0;
    const net = finite(a?.netBeforeFlexW) ? Number(a.netBeforeFlexW) : base - pv;
    const imp = finite(a?.importBeforeFlexW) ? Math.max(0, Number(a.importBeforeFlexW)) : Math.max(0, net);
    const exp = finite(a?.exportBeforeFlexW) ? Math.max(0, Number(a.exportBeforeFlexW))
      : finite(a?.pvSurplusBeforeFlexW) ? Math.max(0, Number(a.pvSurplusBeforeFlexW))
      : Math.max(0, -net);
    return {base,pv,net,imp,exp};
  }

  function renderForecast(root, actions) {
    const forecast = root.querySelector('.pm-forecast');
    const frame = root.querySelector('.pm-forecast-frame');
    if (!forecast || !frame || actions.length !== 96) return;

    updateLegend(root);
    renderAxis(root, actions);

    forecast.classList.add('pm-interactive-chart');
    forecast.replaceChildren();
    frame.querySelectorAll('.pm-crosshair,.pm-hover-tooltip,.pm-scale-hint').forEach(n => n.remove());

    const data = actions.map(derive);
    const maxAbs = Math.max(1000, ...data.flatMap(d => [d.base,d.pv,d.imp,d.exp].map(Math.abs)));
    const scaleMax = Math.ceil(maxAbs / 500) * 500;
    const W = 960, H = 100, zeroY = 50, halfH = 46;
    const yPos = w => zeroY - Math.max(0, w) / scaleMax * halfH;
    const yNeg = w => zeroY + Math.max(0, w) / scaleMax * halfH;
    const slotW = W / 96;

    const svg = svgEl('svg', {viewBox:`0 0 ${W} ${H}`, preserveAspectRatio:'none', role:'img', 'aria-label':'Interactieve 24-uurs forecast'});

    [500,1000].filter(v => v < scaleMax).forEach(v => {
      svg.append(svgEl('line',{x1:0,y1:yPos(v),x2:W,y2:yPos(v),class:'pm-ref-line'}));
    });
    svg.append(svgEl('line',{x1:0,y1:zeroY,x2:W,y2:zeroY,class:'pm-zero-line'}));

    const pvGroup = svgEl('g');
    const netGroup = svgEl('g');
    data.forEach((d,idx) => {
      const x = idx*slotW;
      if (d.pv > 0) {
        const y = yPos(d.pv);
        pvGroup.append(svgEl('rect',{x:x+slotW*.18,y,width:slotW*.27,height:Math.max(.7,zeroY-y),rx:.35,class:'pm-pv-bar'}));
      }
      if (d.imp > 0) {
        const y = yPos(d.imp);
        netGroup.append(svgEl('rect',{x:x+slotW*.58,y,width:slotW*.27,height:Math.max(.7,zeroY-y),rx:.35,class:'pm-import-bar'}));
      }
      if (d.exp > 0) {
        netGroup.append(svgEl('rect',{x:x+slotW*.58,y:zeroY,width:slotW*.27,height:Math.max(.7,yNeg(d.exp)-zeroY),rx:.35,class:'pm-export-bar'}));
      }
    });
    svg.append(pvGroup, netGroup);

    const points = data.map((d,idx) => `${idx*slotW+slotW/2},${yPos(d.base)}`).join(' ');
    const areaPoints = `0,${zeroY} ${points} ${W},${zeroY}`;
    svg.append(svgEl('polygon',{points:areaPoints,class:'pm-base-area'}));
    svg.append(svgEl('polyline',{points,class:'pm-base-line'}));
    forecast.append(svg);

    const cross = document.createElement('div');
    cross.className = 'pm-crosshair';
    const tip = document.createElement('div');
    tip.className = 'pm-hover-tooltip';
    const hint = document.createElement('div');
    hint.className = 'pm-scale-hint';
    hint.textContent = `± ${kw(scaleMax)}`;
    frame.append(cross,tip,hint);

    let pinned = false;
    let selected = null;

    function show(idx, clientX) {
      idx = Math.max(0, Math.min(95, idx));
      selected = idx;
      const a = actions[idx], d = data[idx];
      const direction = d.net < 0 ? 'export' : 'import';
      tip.innerHTML = '';
      const title = document.createElement('strong');
      title.textContent = fullTime(a.start);
      tip.append(title);
      [
        ['base','Base load',d.base],['pv','PV',d.pv],['import','Import',d.imp],['export','Export',d.exp]
      ].forEach(([kind,label,val]) => {
        const row = document.createElement('div'); row.className='pm-hover-row';
        const dot = document.createElement('i'); dot.className=`pm-hover-dot ${kind}`;
        const lab = document.createElement('span'); lab.textContent=label;
        const value = document.createElement('span'); value.textContent=kw(val);
        row.append(dot,lab,value); tip.append(row);
      });
      const net = document.createElement('div'); net.className='pm-hover-net';
      net.textContent = `Netto ${kw(Math.abs(d.net))} ${direction}`;
      tip.append(net);

      const rect = frame.getBoundingClientRect();
      const x = ((idx+.5)/96)*rect.width;
      cross.style.left = `${x}px`; cross.style.display='block'; tip.style.display='block';
      const tw = Math.min(230, tip.offsetWidth || 210);
      const desired = Number.isFinite(clientX) ? clientX-rect.left+12 : x+12;
      tip.style.left = `${Math.max(6, Math.min(rect.width-tw-6, desired))}px`;
      tip.style.top = '8px';
    }

    function idxAt(clientX) {
      const r = frame.getBoundingClientRect();
      return Math.floor(((clientX-r.left)/Math.max(1,r.width))*96);
    }

    frame.addEventListener('pointermove', e => {
      if (pinned || e.pointerType === 'touch') return;
      show(idxAt(e.clientX), e.clientX);
    });
    frame.addEventListener('pointerleave', e => {
      if (pinned || e.pointerType === 'touch') return;
      cross.style.display='none'; tip.style.display='none';
    });
    frame.addEventListener('pointerup', e => {
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      const idx = idxAt(e.clientX);
      if (pinned && selected === idx) {
        pinned = false; cross.style.display='none'; tip.style.display='none';
      } else {
        pinned = true; show(idx,e.clientX);
      }
    });
  }

  async function enhance(root) {
    if (!root || root.dataset.pmInteractive === '1') return;
    const url = root.dataset.plannerUrl;
    if (!url) return;
    try {
      const r = await fetch(`${url}?interactive=${Date.now()}`, {cache:'no-store'});
      if (!r.ok) return;
      const actions = normalizeActions(await r.json());
      if (actions.length !== 96) return;
      root.dataset.pmInteractive = '1';
      renderForecast(root,actions);
    } catch (_) {
      // Existing planner remains intact if the optional enhancement cannot load.
    }
  }

  function scan() {
    installStyles();
    document.querySelectorAll(SELECTOR).forEach(root => {
      const content = root.querySelector('.pm-content');
      if (content && !content.hidden) enhance(root);
      else {
        const obs = new MutationObserver(() => {
          if (content && !content.hidden) { obs.disconnect(); enhance(root); }
        });
        if (content) obs.observe(content,{attributes:true,attributeFilter:['hidden']});
      }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',scan,{once:true});
  else scan();
  if (window.document$?.subscribe) window.document$.subscribe(scan);
})();