(() => {
  const root=document.getElementById('planner-shadow');
  if(!root)return;
  const RAW='https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow.json';
  const BOILER_W_DEFAULT=1900;
  const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
  const num=v=>finite(v)?Number(v):null;
  const fmt=(v,d=1)=>finite(v)?Number(v).toLocaleString('nl-NL',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
  const time=iso=>{const d=new Date(iso);return Number.isNaN(d.getTime())?'—':d.toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'});};
  const dateLabel=iso=>{const d=new Date(iso);return Number.isNaN(d.getTime())?'—':d.toLocaleDateString('nl-NL',{weekday:'short',day:'numeric',month:'short'});};
  const el=(t,c,x)=>{const n=document.createElement(t);if(c)n.className=c;if(x!==undefined)n.textContent=x;return n;};
  const unwrap=payload=>payload?.plan?.plan?.actions?payload.plan:(payload?.plan||payload||{});
  async function load(){for(const u of [root.dataset.source,`${RAW}?ts=${Date.now()}`]){try{if(!u)continue;const r=await fetch(u,{cache:'no-store'});if(r.ok)return await r.json();}catch(_){}}return null;}
  const category=(s,boilerW)=>{
    const pv=Math.max(0,num(s?.pvCoverageW??s?.warmWaterPvCoverageW)||0),grid=Math.max(0,num(s?.gridRequiredW??s?.warmWaterGridRequiredW)||0),reason=String(s?.allocationReason||s?.warmWaterReason||'').toUpperCase();
    if(grid<=1&&(pv>=Math.max(1,boilerW-50)||reason.includes('PV_SURPLUS_FULL')||reason==='PV_FULL'))return 'pv-full';
    if(pv>0||reason.includes('PV_PARTIAL'))return 'pv-partial';
    return 'grid-cheap';
  };
  const categoryLabel=c=>c==='pv-full'?'PV surplus':c==='pv-partial'?'PV + net':'Goedkoop net';
  const categoryReason=(c,s)=>{
    if(c==='pv-full')return 'Volledige boilerlast kan uit voorspeld PV-overschot worden geleverd.';
    if(c==='pv-partial')return 'Dit kwartier gebruikt beschikbaar PV-overschot en vult alleen het resterende vermogen uit het net aan.';
    const p=num(s?.price_eur_kwh);return finite(p)&&p<0?'Na de beste PV-slots is nog WW-energie nodig. Dit negatieve-prijskwartier is daarom een van de goedkoopste resterende slots vóór de deadline.':'Na de beste PV-slots is nog WW-energie nodig. Dit kwartier behoort tot de goedkoopste resterende bruikbare slots vóór de deadline.';
  };
  const nearestAction=(actions,s)=>actions.find(a=>a.start===s.start)||s;
  function render(payload){
    root.querySelector('#ps-ww-multislot')?.remove();
    const p=unwrap(payload),inputs=p.inputs||{},plan=p.plan||{},ww=inputs.warmWater||{},wwPlan=plan.warmWater||{},actions=Array.isArray(plan.actions)?plan.actions:[],allSlots=Array.isArray(wwPlan.allocatedSlots)?wwPlan.allocatedSlots:[];
    const boilerW=num(ww.modeledPowerW)||BOILER_W_DEFAULT;
    const grouped=new Map();
    allSlots.forEach(s=>{const key=s.planningDate||s.localDate||String(s.start||'').slice(0,10)||'unknown';if(!grouped.has(key))grouped.set(key,[]);grouped.get(key).push(s);});
    const sec=el('section','ps-section ps-ww-multislot');sec.id='ps-ww-multislot';
    sec.append(el('h2','','Boiler plan · waarom deze kwartieren?'));
    sec.append(el('div','ps-chart-note','De boiler blijft turquoise als asset. Vulling en patroon tonen waarom een kwartier is gekozen: volledig PV-overschot, gedeeltelijk PV + net, of goedkoop net. Klik op een kwartier voor uitleg.'));
    const legend=el('div','ps-ww-legend');
    [['PV surplus','pv-full'],['PV + net','pv-partial'],['Goedkoop net','grid-cheap']].forEach(([label,c])=>{const item=el('span');item.append(el('i',`ps-ww-key ${c}`),document.createTextNode(label));legend.append(item);});sec.append(legend);
    if(!allSlots.length){sec.append(el('div','ps-ww-state',ww.goalReachedToday?'Geen boilerplanning nodig: het dagdoel is bereikt.':'Er zijn momenteel geen WW-slots toegewezen.'));root.append(sec);return;}
    grouped.forEach((slots,dateKey)=>{
      slots.sort((a,b)=>Date.parse(a.start)-Date.parse(b.start));
      const block=el('div','ps-ww-day');
      const first=slots[0],dateTitle=el('div','ps-ww-day-title',`${dateLabel(first.start)} · ${fmt(slots.reduce((sum,s)=>sum+(num(s.allocatedKWh)||0),0),2)} kWh gepland`);block.append(dateTitle);
      const row=el('div','ps-ww-timeline-row'),name=el('div','ps-action-name','Boiler'),track=el('div','ps-ww-timeline-track');row.append(name,track);
      const actionIndex=new Map(actions.map((a,i)=>[a.start,i]));
      slots.forEach((s,slotIdx)=>{
        const idx=actionIndex.has(s.start)?actionIndex.get(s.start):null;if(idx===null)return;
        const action=nearestAction(actions,s),merged={...action,...s},c=category(merged,boilerW),button=el('button',`ps-ww-slot-segment ${c}`);button.type='button';button.style.gridColumn=`${idx+1} / ${idx+2}`;button.dataset.slot=String(slotIdx);button.dataset.date=dateKey;button.setAttribute('aria-label',`${time(s.start)}–${time(s.end)} · ${categoryLabel(c)}`);button.title=`${time(s.start)}–${time(s.end)} · ${categoryLabel(c)} · PV ${fmt(merged.pvCoverageW??merged.warmWaterPvCoverageW,0)} W · net ${fmt(merged.gridRequiredW??merged.warmWaterGridRequiredW,0)} W`;track.append(button);
      });block.append(row);
      const details=el('div','ps-ww-detail');
      const detailHead=el('div','ps-ww-detail-head'),detailTitle=el('strong','ps-ww-detail-title'),badge=el('span','ps-ww-detail-badge');detailHead.append(detailTitle,badge);details.append(detailHead);
      const metrics=el('div','ps-ww-detail-metrics');['Boiler','PV-dekking','Net nodig','Prijs'].forEach(label=>{const cell=el('div','ps-ww-detail-metric');cell.append(el('span','',label),el('strong',''));metrics.append(cell);});details.append(metrics);details.append(el('div','ps-ww-detail-why-title','Waarom dit slot?'),el('div','ps-ww-detail-reason'));
      block.append(details);
      const summary=el('div','ps-ww-summary');
      const energy={"pv-full":0,"pv-partial":0,"grid-cheap":0};slots.forEach(s=>{const a=nearestAction(actions,s),c=category({...a,...s},boilerW);energy[c]+=num(s.allocatedKWh)||0;});
      const total=Object.values(energy).reduce((a,b)=>a+b,0),deadline=slots.find(s=>s.deadlineLocal)?.deadlineLocal||ww.deadlineLocal||'19:00';
      const summaryTitle=el('div','ps-ww-summary-title',`Boiler ${dateLabel(first.start)} · ${fmt(total,2)} kWh`);summary.append(summaryTitle);
      [['PV surplus','pv-full'],['PV + net','pv-partial'],['Goedkoop net','grid-cheap']].forEach(([label,c])=>{const r=el('div','ps-ww-summary-row');r.append(el('span','',label),el('strong','',`${fmt(energy[c],2)} kWh`));summary.append(r);});
      const foot=el('div','ps-ww-summary-foot',`Deadline ${deadline} · strategie: PV eerst → resterend goedkoop net`);summary.append(foot);block.append(summary);
      const select=s=>{const a=nearestAction(actions,s),m={...a,...s},c=category(m,boilerW),pv=Math.max(0,num(m.pvCoverageW??m.warmWaterPvCoverageW)||0),grid=Math.max(0,num(m.gridRequiredW??m.warmWaterGridRequiredW)||0),price=num(m.price_eur_kwh),end=s.end||new Date(Date.parse(s.start)+15*60000).toISOString();detailTitle.textContent=`${time(s.start)}–${time(end)} · ${categoryLabel(c)}`;badge.textContent=c==='pv-full'?'PV':c==='pv-partial'?'PV + NET':'NET';badge.className=`ps-ww-detail-badge ${c}`;const vals=[`${fmt(boilerW,0)} W`,`${fmt(pv,0)} W`,`${fmt(grid,0)} W`,finite(price)?`${price<0?'−':''}€ ${fmt(Math.abs(price),4)}/kWh`:'—'];[...metrics.children].forEach((cell,i)=>cell.querySelector('strong').textContent=vals[i]);details.querySelector('.ps-ww-detail-reason').textContent=categoryReason(c,m);track.querySelectorAll('.ps-ww-slot-segment').forEach(b=>b.classList.toggle('selected',b.dataset.slot===String(slots.indexOf(s))));};
      track.querySelectorAll('.ps-ww-slot-segment').forEach(button=>button.addEventListener('click',()=>select(slots[Number(button.dataset.slot)])));
      select(slots[0]);sec.append(block);
    });
    const policy=wwPlan.allocationPolicy||'—';sec.append(el('div','ps-ww-foot',`Plannerpolicy: ${String(policy).replaceAll('_',' ').toLowerCase()} · visualisatie is alleen uitleg van SHADOW-planning; geen aansturingswijziging.`));
    const anchor=[...root.querySelectorAll('.ps-section')].find(x=>x!==sec&&x.textContent.includes('Verplichtingen & datakwaliteit'));
    if(anchor)root.insertBefore(sec,anchor);else root.append(sec);
  }
  load().then(p=>{if(p)render(p);});
})();