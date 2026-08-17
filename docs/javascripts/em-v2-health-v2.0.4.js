(function(){
  'use strict';
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
    header.appendChild(b);
    return b;
  }
  function removeDetail(){
    const d=document.getElementById('em-v2-health-detail');
    if(d) d.remove();
  }
  function render(detail){
    removeDetail();
    const status=statusOf(detail);
    const mode=detail?.controlMode||'UNKNOWN';
    const badge=ensureBadge();
    if(badge){
      badge.dataset.status=status.replace(' ','-').toLowerCase();
      badge.textContent=`EM v2 · ${status} · ${mode}`;
      badge.title=detail?`State ${fmtAge(detail.stateAgeMs)} oud · heartbeat ${fmtAge(detail.heartbeatAgeMs)} oud`:'Geen geldige v2-state';
    }
  }
  function rerender(){render(window.EnergyCoreV2?.state||null);}
  document.addEventListener('energycorev2state',e=>render(e.detail));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(rerender,800));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(rerender,100));
})();
