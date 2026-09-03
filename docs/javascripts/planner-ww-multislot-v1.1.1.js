(() => {
  const root=document.getElementById('planner-shadow');
  if(!root)return;
  const RAW='https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow.json';
  const BOILER_W_DEFAULT=1900;
  const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
  const num=v=>finite(v)?Number(v):null;
  const fmt=(v,d=1)=>finite(v)?Number(v).toLocaleString('nl-NL',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
  const time=iso=>{const d=new Date(iso);return Number.isNaN(d.getTime())?'—':d.toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'});};
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
    if(c==='pv-partial')return 'Beschikbaar PV-overschot dekt een deel van de boilerlast; alleen het restant komt uit het net.';
    const p=num(s?.price_eur_kwh);return finite(p)&&p<0?'Na de beste PV-slots is nog WW-energie nodig. Dit negatieve-prijskwartier vult die resterende behoefte goedkoop in vóór de deadline.':'Na de beste PV-slots is nog WW-energie nodig. Dit behoort tot de goedkoopste resterende bruikbare kwartieren vóór de deadline.';
  };
  const nearestAction=(actions,s)=>actions.find(a=>a.start===s.start)||s;
  function findPrimaryBoilerRow(){
    const isBoiler=r=>['Boiler','Boiler plan'].includes(String(r.querySelector('.ps-action-name')?.textContent||'').trim());
    const moved=root.querySelector('#ps-forecast-load-windows');
    const movedRow=moved?[...moved.querySelectorAll(':scope > .ps-action-row')].find(isBoiler):null;
    if(movedRow)return movedRow;
    const plannerSection=[...root.querySelectorAll('.ps-section')].find(s=>s.querySelector('.ps-price-chart')&&s.textContent.includes('Prijs'));
    return plannerSection?[...plannerSection.querySelectorAll(':scope > .ps-action-row')].find(isBoiler)||null:null;
  }
  function render(payload){
    root.querySelector('#ps-ww-multislot')?.remove();
    root.querySelector('#ps-ww-inline-detail')?.remove();
    const row=findPrimaryBoilerRow();
    if(!row)return;
    const p=unwrap(payload),inputs=p.inputs||{},plan=p.plan||{},ww=inputs.warmWater||{},wwPlan=plan.warmWater||{},actions=Array.isArray(plan.actions)?plan.actions:[],allSlots=Array.isArray(wwPlan.allocatedSlots)?wwPlan.allocatedSlots:[];
    const track=row.querySelector('.ps-action-track');if(!track)return;
    const boilerW=num(ww.modeledPowerW)||BOILER_W_DEFAULT;
    const actionIndex=new Map(actions.map((a,i)=>[a.start,i]));
    track.replaceChildren();
    row.classList.add('ps-ww-primary-owner','ps-forecast-row');
    const name=row.querySelector('.ps-action-name');if(name)name.textContent='Boiler plan';
    const slots=allSlots.filter(s=>actionIndex.has(s.start)).sort((a,b)=>Date.parse(a.start)-Date.parse(b.start));
    slots.forEach((s,slotIdx)=>{
      const idx=actionIndex.get(s.start),merged={...nearestAction(actions,s),...s},c=category(merged,boilerW),button=el('button',`ps-ww-slot-segment ${c}`);
      button.type='button';button.style.gridColumn=`${idx+1} / ${idx+2}`;button.dataset.slot=String(slotIdx);
      button.setAttribute('aria-label',`${time(s.start)}–${time(s.end)} · ${categoryLabel(c)}`);
      button.title=`${time(s.start)}–${time(s.end)} · ${categoryLabel(c)} · PV ${fmt(merged.pvCoverageW??merged.warmWaterPvCoverageW,0)} W · net ${fmt(merged.gridRequiredW??merged.warmWaterGridRequiredW,0)} W`;
      track.append(button);
    });
    const panel=el('div','ps-ww-inline-detail');panel.id='ps-ww-inline-detail';
    const legend=el('div','ps-ww-legend');[['PV surplus','pv-full'],['PV + net','pv-partial'],['Goedkoop net','grid-cheap']].forEach(([label,c])=>{const item=el('span');item.append(el('i',`ps-ww-key ${c}`),document.createTextNode(label));legend.append(item);});panel.append(legend);
    if(!slots.length){panel.append(el('div','ps-ww-state',ww.goalReachedToday?'Geen boilerplanning nodig: het dagdoel is bereikt.':'Er zijn momenteel geen WW-slots toegewezen.'));row.after(panel);return;}
    const detail=el('div','ps-ww-detail'),head=el('div','ps-ww-detail-head'),title=el('strong','ps-ww-detail-title'),badge=el('span','ps-ww-detail-badge');head.append(title,badge);detail.append(head);
    const metrics=el('div','ps-ww-detail-metrics');['Boiler','PV-dekking','Net nodig','Prijs'].forEach(label=>{const cell=el('div','ps-ww-detail-metric');cell.append(el('span','',label),el('strong',''));metrics.append(cell);});detail.append(metrics,el('div','ps-ww-detail-why-title','Waarom dit slot?'),el('div','ps-ww-detail-reason'));panel.append(detail);
    const summary=el('div','ps-ww-summary'),energy={'pv-full':0,'pv-partial':0,'grid-cheap':0};slots.forEach(s=>{const m={...nearestAction(actions,s),...s};energy[category(m,boilerW)]+=num(s.allocatedKWh)||0;});
    const total=Object.values(energy).reduce((a,b)=>a+b,0);summary.append(el('div','ps-ww-summary-title',`Boiler gepland · ${fmt(total,2)} kWh`));[['PV surplus','pv-full'],['PV + net','pv-partial'],['Goedkoop net','grid-cheap']].forEach(([label,c])=>{const r=el('div','ps-ww-summary-row');r.append(el('span','',label),el('strong','',`${fmt(energy[c],2)} kWh`));summary.append(r);});summary.append(el('div','ps-ww-summary-foot',`Deadline ${ww.deadlineLocal||'19:00'} · strategie: PV eerst → resterend goedkoop net`));panel.append(summary);row.after(panel);
    const select=(s,slotIdx)=>{const m={...nearestAction(actions,s),...s},c=category(m,boilerW),pv=Math.max(0,num(m.pvCoverageW??m.warmWaterPvCoverageW)||0),grid=Math.max(0,num(m.gridRequiredW??m.warmWaterGridRequiredW)||0),price=num(m.price_eur_kwh),end=s.end||new Date(Date.parse(s.start)+15*60000).toISOString();title.textContent=`${time(s.start)}–${time(end)} · ${categoryLabel(c)}`;badge.textContent=c==='pv-full'?'PV':c==='pv-partial'?'PV + NET':'NET';badge.className=`ps-ww-detail-badge ${c}`;const vals=[`${fmt(boilerW,0)} W`,`${fmt(pv,0)} W`,`${fmt(grid,0)} W`,finite(price)?`${price<0?'−':''}€ ${fmt(Math.abs(price),4)}/kWh`:'—'];[...metrics.children].forEach((cell,i)=>cell.querySelector('strong').textContent=vals[i]);detail.querySelector('.ps-ww-detail-reason').textContent=categoryReason(c,m);track.querySelectorAll('.ps-ww-slot-segment').forEach(b=>b.classList.toggle('selected',b.dataset.slot===String(slotIdx)));};
    track.querySelectorAll('.ps-ww-slot-segment').forEach((button,i)=>button.addEventListener('click',()=>select(slots[i],i)));select(slots[0],0);
  }
  load().then(p=>{if(p)render(p);});
})();