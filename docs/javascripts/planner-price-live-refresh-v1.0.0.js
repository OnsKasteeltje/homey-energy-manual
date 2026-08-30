(() => {
  const ROOT_ID='planner-shadow';
  const RAW='https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow.json';
  const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
  const price=a=>finite(a?.price_eur_kwh)?Number(a.price_eur_kwh):finite(a?.price)?Number(a.price):null;
  const actionsFrom=p=>Array.isArray(p?.plan?.plan?.actions)?p.plan.plan.actions:Array.isArray(p?.plan?.actions)?p.plan.actions:[];
  const cls=a=>String(a?.priceClass||a?.class||'normal').toLowerCase();
  const fmt=v=>Number(v).toLocaleString('nl-NL',{minimumFractionDigits:2,maximumFractionDigits:3});
  const fmt3=v=>Number(v).toLocaleString('nl-NL',{minimumFractionDigits:3,maximumFractionDigits:3});
  const time=iso=>{const d=new Date(iso);return Number.isNaN(d.getTime())?'—':d.toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'});};

  function updateAxis(root,prices){
    const axis=root.querySelector('.ps-y-axis-price');
    if(!axis||!prices.length)return;
    const pos=Math.max(0.01,...prices.filter(v=>v>=0));
    const neg=Math.min(0,...prices.filter(v=>v<0));
    const labels=[[`€ ${fmt(pos)}`,3],[`€ ${fmt(pos/2)}`,40],['€ 0,00',78]];
    if(neg<0)labels.push([`€ ${fmt(neg)}`,98]);
    axis.replaceChildren(...labels.map(([text,top])=>{const s=document.createElement('span');s.className='ps-y-axis-label';s.style.top=`${top}%`;s.textContent=text;return s;}));
  }

  function apply(root,payload){
    const actions=actionsFrom(payload);
    const cols=[...root.querySelectorAll('.ps-price-col')];
    if(!actions.length||cols.length!==actions.length)return false;
    const prices=actions.map(price);
    const known=prices.filter(Number.isFinite);
    if(!known.length)return false;
    const posMax=Math.max(.001,...known.filter(p=>p>0));
    const negAbsMax=Math.max(.001,...known.filter(p=>p<0).map(p=>Math.abs(p)));
    cols.forEach((col,idx)=>{
      const a=actions[idx],p=prices[idx],bar=col.querySelector('.ps-price-bar');
      if(!bar)return;
      bar.classList.remove('cheap','normal','expensive','negative','unknown');
      bar.classList.add(cls(a));
      if(Number.isFinite(p)){
        if(p<0){bar.classList.add('negative');bar.style.height=`${Math.max(2,Math.min(22,Math.abs(p)/negAbsMax*22))}%`;}
        else bar.style.height=`${Math.max(2,Math.min(78,p/posMax*78))}%`;
        bar.title=`${time(a.start)} · € ${fmt3(p)}/kWh`;
      }else{
        bar.classList.add('unknown');bar.style.height='4%';bar.title=`${time(a.start)} · prijs —`;
      }
    });
    root.querySelectorAll('.ps-price-unavailable-zone').forEach(n=>n.remove());
    const chart=root.querySelector('.ps-price-chart');
    if(chart)chart.dataset.priceAvailability='0';
    updateAxis(root,known);
    root.dataset.priceRevision=String(payload?.sourceRevision??payload?.plan?.inputs?.sourceRevision??payload?.plan?.sourceRevision??'');
    return true;
  }

  async function refresh(){
    const root=document.getElementById(ROOT_ID);if(!root)return;
    try{
      const r=await fetch(`${RAW}?priceRefresh=${Date.now()}`,{cache:'no-store'});
      if(!r.ok)return;
      const payload=await r.json();
      apply(root,payload);
    }catch(_){/* keep existing render */}
  }

  refresh();
  const timer=setInterval(refresh,30000);
  addEventListener('focus',refresh);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
})();
