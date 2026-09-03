(() => {
  const root=document.getElementById('planner-shadow'); if(!root)return;
  const src=root.dataset.source||'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow.json?source=planner-action-details';
  const time=iso=>{const d=new Date(iso);return Number.isNaN(d.getTime())?'—':d.toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'});};
  const fmt=(v,d=0)=>Number.isFinite(Number(v))?Number(v).toLocaleString('nl-NL',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
  const unwrap=x=>x?.plan?.plan?.actions?x.plan:(x?.plan||x||{});
  const active=a=>{const v=String(a?.tesla||'HOLD').toUpperCase();return !['HOLD','NONE','OFF',''].includes(v);};
  const targetW=a=>{for(const v of [a?.teslaTargetW,a?.evTargetW,a?.targetW])if(Number.isFinite(Number(v))&&Number(v)!==0)return Math.abs(Number(v));return null;};
  const runs=actions=>{const out=[];let s=null;for(let i=0;i<=actions.length;i++){const on=i<actions.length&&active(actions[i]);if(on&&s===null)s=i;if(!on&&s!==null){out.push([s,i]);s=null;}}return out;};
  const findTeslaRow=()=>{
    const isTesla=r=>['Tesla','Tesla plan'].includes(r.querySelector('.ps-action-name')?.textContent?.trim());
    const moved=root.querySelector('#ps-forecast-load-windows');
    const movedRow=moved?[...moved.querySelectorAll(':scope > .ps-action-row')].find(isTesla):null;
    if(movedRow)return movedRow;
    const price=[...root.querySelectorAll('.ps-section')].find(s=>s.querySelector('h2')?.textContent?.trim()==='Prijs & planneracties');
    return price?[...price.querySelectorAll(':scope > .ps-action-row')].find(isTesla)||null:null;
  };
  const style=()=>{if(document.getElementById('ps-action-detail-style'))return;const s=document.createElement('style');s.id='ps-action-detail-style';s.textContent=`
    .ps-action-segment{position:relative;cursor:help;overflow:visible!important}
    .ps-action-segment .ps-action-popover{display:none;position:absolute;z-index:40;left:50%;bottom:calc(100% + 8px);transform:translateX(-50%);min-width:230px;max-width:310px;padding:10px 12px;border:1px solid rgba(127,127,127,.28);border-radius:10px;background:var(--md-default-bg-color,#fff);box-shadow:0 8px 24px rgba(0,0,0,.16);color:var(--md-default-fg-color,#222);font-size:.78rem;line-height:1.35;white-space:normal;text-align:left}
    .ps-action-segment:hover .ps-action-popover,.ps-action-segment:focus .ps-action-popover,.ps-action-segment.ps-popover-open .ps-action-popover{display:block}
    .ps-action-popover strong{display:block;font-size:.86rem;margin-bottom:5px}.ps-action-popover div+div{margin-top:2px}
    .ps-action-segment.ps-action-invalid{outline:2px solid currentColor;outline-offset:2px}
  `;document.head.append(s);};
  const apply=data=>{
    style();
    const p=unwrap(data),actions=Array.isArray(p?.plan?.actions)?p.plan.actions:[],tesla=p?.inputs?.tesla||{};
    const policy=String(tesla?.opportunityPolicy||'').toUpperCase(),startThreshold=Number(tesla?.opportunityStartMinW||4830),continueThreshold=Number(tesla?.opportunityContinueMinW||4140),deadline=tesla?.deadlineActive===true;
    const row=findTeslaRow();if(!row)return;
    const segments=[...row.querySelectorAll('.ps-action-segment.tesla')],groups=runs(actions);
    segments.forEach((seg,idx)=>{
      const g=groups[idx]; if(!g)return; const [start,end]=g,slots=actions.slice(start,end),first=actions[start],last=actions[end-1];
      const endIso=last?.end||new Date(new Date(last.start).getTime()+15*60000).toISOString(),mins=(end-start)*15;
      const raw=String(first?.tesla||'—').replaceAll('_',' '),rawUpper=raw.toUpperCase();
      const isDeadline=deadline||rawUpper.includes('DEADLINE')||rawUpper.includes('MUST');
      const isOpportunity=!isDeadline&&(policy.includes('PV_SURPLUS')||rawUpper.includes('OPPORTUNITY'));
      const why=isDeadline?'Deadline':isOpportunity?'PV opportunity':'Tesla forecast';
      const surplusVals=slots.map(a=>Math.max(0,Number(a?.pvSurplusBeforeFlexW)||0)),minSurplus=Math.min(...surplusVals),maxSurplus=Math.max(...surplusVals);
      const pvValid=!isOpportunity||(surplusVals[0]>=startThreshold&&surplusVals.slice(1).every(v=>v>=continueThreshold));
      const power=targetW(first),kwh=power?power*mins/60000:null;
      seg.classList.toggle('ps-action-invalid',!pvValid);seg.tabIndex=0;seg.textContent=(end-start)>=3?`${time(first.start)}–${time(endIso)}`:'';
      const pop=document.createElement('div');pop.className='ps-action-popover';
      const status=isDeadline?'Geldig deadline-slot volgens huidige policy':pvValid?'Geldig volgens huidige opportunity-policy':`LET OP: start vereist ≥ ${fmt(startThreshold)} W en vervolgslots ≥ ${fmt(continueThreshold)} W PV-overschot`;
      const thresholdLine=isDeadline?'<div>Opportunity-drempel: n.v.t. bij deadline</div>':isOpportunity?`<div>PV-startdrempel: ${fmt(startThreshold)} W</div><div>PV-doorgaan-drempel: ${fmt(continueThreshold)} W</div>`:'<div>Opportunity-drempel: n.v.t.</div>';
      const reason=isDeadline?(maxSurplus>=startThreshold?'PV-overschot vóór deadline':'Deadline vereist energie; slot geselecteerd via deadline-optimalisatie'):(isOpportunity?'PV-overschot voldoet aan opportunity-hysterese':'Plannerforecast');
      pop.innerHTML=`<strong>Tesla · ${why}</strong><div>${time(first.start)}–${time(endIso)} · ${mins} min</div><div>PV-overschot: ${fmt(minSurplus)}–${fmt(maxSurplus)} W</div>${thresholdLine}<div>Reden: ${reason}</div><div>Planvermogen: ${power?`${fmt(power)} W`:'niet gepubliceerd'}</div><div>Planbare energie: ${kwh?`ca. ${fmt(kwh,2)} kWh`:'niet betrouwbaar berekenbaar'}</div><div>Validatie: ${status}</div><div>Planneractie: ${raw}</div>`;
      seg.append(pop);seg.title='';
      seg.addEventListener('click',e=>{e.stopPropagation();seg.classList.toggle('ps-popover-open');});
      seg.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();seg.classList.toggle('ps-popover-open');}if(e.key==='Escape')seg.classList.remove('ps-popover-open');});
    });
    document.addEventListener('click',()=>segments.forEach(s=>s.classList.remove('ps-popover-open')),{once:true});
  };
  fetch(src,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}).then(apply).catch(e=>console.warn('Planner action details konden niet laden',e));
})();