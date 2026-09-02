(() => {
  const root=document.getElementById('planner-shadow');
  if(!root)return;

  const STYLE_ID='ps-price-availability-style';
  const ensureStyle=()=>{
    if(document.getElementById(STYLE_ID))return;
    const s=document.createElement('style');
    s.id=STYLE_ID;
    s.textContent=`
      #planner-shadow .ps-price-chart{position:relative}
      #planner-shadow .ps-price-unavailable-zone{position:absolute;top:0;bottom:0;z-index:1;pointer-events:none;border-left:1px dashed var(--md-default-fg-color--lightest);background:repeating-linear-gradient(135deg,color-mix(in srgb,var(--md-default-fg-color) 5%,transparent) 0 6px,transparent 6px 12px)}
      #planner-shadow .ps-price-unavailable-label{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);padding:.2rem .45rem;border-radius:.35rem;background:color-mix(in srgb,var(--md-default-bg-color) 88%,transparent);color:var(--md-default-fg-color--light);font-size:.7rem;font-weight:700;white-space:nowrap}
      #planner-shadow .ps-price-bar.unknown{opacity:.18}
    `;
    document.head.append(s);
  };

  const priceSection=()=>[...root.querySelectorAll(':scope > section.ps-section')]
    .find(section=>section.querySelector(':scope > h2')?.textContent.trim()==='Prijs & planneracties')||null;

  const contract=()=>{
    const summary=String(root.querySelector('.ps-summary span')?.textContent||'').toUpperCase();
    if(summary.includes('· FIXED ·')||summary.includes('· VAST ·'))return 'FIXED';
    if(summary.includes('· DYNAMIC ·')||summary.includes('· DYNAMISCH ·'))return 'DYNAMIC';
    return 'UNKNOWN';
  };

  const updateContractVisibility=()=>{
    const section=priceSection();
    if(!section)return;
    const fixed=contract()==='FIXED';
    section.hidden=fixed;
    section.style.display=fixed?'none':'';
    section.dataset.hiddenForContract=fixed?'FIXED':'';
  };

  const decorate=chart=>{
    if(!chart||chart.dataset.priceAvailability==='1')return;
    const cols=[...chart.querySelectorAll('.ps-price-col')];
    if(!cols.length)return;
    const unknown=cols.map(c=>!!c.querySelector('.ps-price-bar.unknown'));
    let start=-1;
    for(let i=unknown.length-1;i>=0;i--){
      if(unknown[i])start=i;
      else break;
    }
    if(start<0||start===unknown.length)return;
    ensureStyle();
    const zone=document.createElement('div');
    zone.className='ps-price-unavailable-zone';
    zone.style.left=`${(start/unknown.length)*100}%`;
    zone.style.width=`${((unknown.length-start)/unknown.length)*100}%`;
    const label=document.createElement('span');
    label.className='ps-price-unavailable-label';
    label.textContent='Prijs nog niet beschikbaar';
    zone.append(label);
    chart.append(zone);
    chart.dataset.priceAvailability='1';
  };

  const scan=()=>{
    updateContractVisibility();
    if(contract()!=='FIXED')root.querySelectorAll('.ps-price-chart').forEach(decorate);
  };
  scan();
  new MutationObserver(scan).observe(root,{childList:true,subtree:true});
})();
