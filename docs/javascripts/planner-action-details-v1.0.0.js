(() => {
  const root=document.getElementById('planner-shadow'); if(!root)return;
  const src=root.dataset.source||'https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-planner-shadow.json?source=planner-action-details';
  const time=iso=>{const d=new Date(iso);return Number.isNaN(d.getTime())?'—':d.toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'});};
  const fmt=(v,d=0)=>Number.isFinite(Number(v))?Number(v).toLocaleString('nl-NL',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
  const unwrap=x=>x?.plan?.plan?.actions?x.plan:(x?.plan||x||{});
  const active=a=>{const v=String(a?.tesla||'HOLD').toUpperCase();return !['HOLD','NONE','OFF',''].includes(v);};
  const reason=(a,tesla)=>{
    const raw=String(a?.tesla||'').toUpperCase();
    if(raw.includes('DEADLINE')||raw.includes('MUST'))return 'Deadline';
    if(raw.includes('PV')||Number(a?.pvSurplusBeforeFlexW||0)>=Number(tesla?.opportunityMinW||800))return 'PV opportunity';
    return 'Tesla forecast';
  };
  const targetW=a=>{for(const v of [a?.teslaTargetW,a?.evTargetW,a?.targetW])if(Number.isFinite(Number(v))&&Number(v)!==0)return Math.abs(Number(v));return null;};
  const runs=actions=>{const out=[];let s=null;for(let i=0;i<=actions.length;i++){const on=i<actions.length&&active(actions[i]);if(on&&s===null)s=i;if(!on&&s!==null){out.push([s,i]);s=null;}}return out;};
  const apply=data=>{
    const p=unwrap(data),actions=Array.isArray(p?.plan?.actions)?p.plan.actions:[],tesla=p?.inputs?.tesla||{};
    const section=[...root.querySelectorAll('.ps-section')].find(s=>s.querySelector('h2')?.textContent?.trim()==='Prijs & planneracties');
    const row=[...(section?.querySelectorAll('.ps-action-row')||[])].find(r=>r.querySelector('.ps-action-name')?.textContent?.trim()==='Tesla');
    if(!row)return;
    const segments=[...row.querySelectorAll('.ps-action-segment.tesla')],groups=runs(actions);
    segments.forEach((seg,idx)=>{
      const g=groups[idx]; if(!g)return; const [start,end]=g,first=actions[start],last=actions[end-1];
      const why=reason(first,tesla),endIso=last?.end||new Date(new Date(last.start).getTime()+15*60000).toISOString();
      const surplus=Math.max(0,...actions.slice(start,end).map(a=>Number(a?.pvSurplusBeforeFlexW)||0));
      const power=targetW(first),mins=(end-start)*15,kwh=power?power*mins/60000:null;
      seg.textContent=`${time(first.start)}–${time(endIso)} · ${why}`;
      seg.title=[`Tesla forecast`,`${time(first.start)}–${time(endIso)}`,`Reden: ${why}`,`Verwacht PV-overschot: ${fmt(surplus)} W`,power?`Planvermogen: ${fmt(power)} W`:'Planvermogen: niet gepubliceerd',kwh?`Geplande energie: ca. ${fmt(kwh,2)} kWh`:'Geplande energie: niet betrouwbaar berekenbaar',`Planneractie: ${String(first?.tesla||'—').replaceAll('_',' ')}`].join('\n');
    });
  };
  fetch(src,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}).then(apply).catch(e=>console.warn('Planner action details konden niet laden',e));
})();