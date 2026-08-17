(function(){
  'use strict';
  const DETAIL_PATHS=['/homey-energy-manual/','/homey-energy-manual/live-energie/','/homey-energy-manual/energy-core-v2/'];
  function fmtAge(ms){
    if(ms==null||!Number.isFinite(ms)) return 'onbekend';
    const m=Math.max(0,Math.round(ms/60000));
    return m<1?'<1 min':`${m} min`;
  }
  function statusOf(detail){
    if(!detail) return 'NO DATA';
    if(!detail.heartbeatFresh) return 'OFFLINE';
    if(!detail.stateFresh) return 'STALE';
    return 'LIVE';
  }
  function ensureBadge(){
    let b=document.getElementById('em-v2-health-badge');
    if(b) return b;
    const header=document.querySelector('.md-header__inner')||document.querySelector('.md-header');
    if(!header) return null;
    b=document.createElement('button');
    b.id='em-v2-health-badge';
    b.type='button';
    b.className='em-v2-health-badge';
    b.setAttribute('aria-label','Energy Management v2 status');
    b.addEventListener('click',()=>{
      const d=document.getElementById('em-v2-health-detail');
      if(d) d.scrollIntoView({behavior:'smooth',block:'center'});
    });
    header.appendChild(b);
    return b;
  }
  function ensureDetail(){
    const path=location.pathname.endsWith('/')?location.pathname:location.pathname+'/';
    if(!DETAIL_PATHS.includes(path)){
      const old=document.getElementById('em-v2-health-detail'); if(old) old.remove();
      return null;
    }
    let d=document.getElementById('em-v2-health-detail');
    if(d) return d;
    const host=document.querySelector('.md-content__inner')||document.querySelector('main');
    if(!host) return null;
    d=document.createElement('div');
    d.id='em-v2-health-detail';
    d.className='em-v2-health-detail';
    host.insertBefore(d,host.firstChild);
    return d;
  }
  function render(detail){
    const status=statusOf(detail);
    const mode=detail?.controlMode||'UNKNOWN';
    const badge=ensureBadge();
    if(badge){
      badge.dataset.status=status.replace(' ','-').toLowerCase();
      badge.textContent=`EM v2 · ${status} · ${mode}`;
      badge.title=detail?`State ${fmtAge(detail.stateAgeMs)} oud · heartbeat ${fmtAge(detail.heartbeatAgeMs)} oud`:'Geen geldige v2-state';
    }
    const d=ensureDetail();
    if(!d) return;
    if(!detail){d.innerHTML='<strong>EM v2: NO DATA</strong> · geen geldige Energy Core v2-state beschikbaar';return;}
    const meta=detail.raw?.meta||{};
    d.innerHTML=`<strong>EM v2: ${status}</strong><span>state ${fmtAge(detail.stateAgeMs)} oud · heartbeat ${fmtAge(detail.heartbeatAgeMs)} oud · revision ${meta.state_revision??'?'} · ${mode}</span>`;
  }
  function rerender(){render(window.EnergyCoreV2?.state||null);}
  document.addEventListener('energycorev2state',e=>render(e.detail));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(rerender,800));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(rerender,100));
})();
