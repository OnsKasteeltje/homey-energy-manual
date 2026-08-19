(function(){
'use strict';
const BASE='/homey-energy-manual/data/';
const FETCH_INTERVAL=5*60*1000;
const LABEL_INTERVAL=60*1000;
let snapshot=null,fetchTimer=null,labelTimer=null;
const fmtAge=sec=>{sec=Math.max(0,Math.round(Number(sec)||0));if(sec<60)return 'zojuist';const min=Math.round(sec/60);if(min<60)return `${min} min geleden`;const h=Math.floor(min/60),m=min%60;return m?`${h} u ${m} min geleden`:`${h} u geleden`;};
function severity(ageSec){if(!Number.isFinite(ageSec))return 'error';if(ageSec>1800)return 'error';if(ageSec>900)return 'warn';return 'ok';}
function render(){
  const el=document.querySelector('#energy-history-dashboard .eh-toolbar .eh-period');
  if(!el||!snapshot)return;
  const now=Date.now(),generatedMs=Date.parse(snapshot.generated_at||''),feedAge=Number.isFinite(generatedMs)?Math.max(0,(now-generatedMs)/1000):NaN;
  const h=snapshot.health||{},sourceMs=Date.parse(h.source_sample_at||''),sourceAge=Number.isFinite(sourceMs)?Math.max(0,(now-sourceMs)/1000):Number(h.source_age_sec);
  const level=severity(Math.max(Number.isFinite(feedAge)?feedAge:Infinity,Number.isFinite(sourceAge)?sourceAge:0));
  el.classList.remove('eh-freshness-ok','eh-freshness-warn','eh-freshness-error');
  el.classList.add(`eh-freshness-${level}`);
  const prefix=level==='ok'?'Actueel':level==='warn'?'Let op: vertraagd':'Data verouderd';
  const feedText=Number.isFinite(feedAge)?fmtAge(feedAge):'onbekende publicatietijd';
  const sourceText=Number.isFinite(sourceAge)?` · bron ${fmtAge(sourceAge)}`:'';
  el.textContent=`${prefix} · bijgewerkt ${feedText}${sourceText}`;
  el.title=`Waarschuwing vanaf 15 min; foutstatus vanaf 30 min. Bron-schema: ${h.source_schema||'onbekend'}`;
}
async function fetchHealth(){
  if(document.hidden||!document.getElementById('energy-history-dashboard'))return;
  try{const r=await fetch(`${BASE}energy-day-v2.json?ts=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(String(r.status));snapshot=await r.json();render();}
  catch(e){const el=document.querySelector('#energy-history-dashboard .eh-toolbar .eh-period');if(el){el.classList.remove('eh-freshness-ok','eh-freshness-warn');el.classList.add('eh-freshness-error');el.textContent='Data-status niet bereikbaar';}}
}
function start(){clearInterval(fetchTimer);clearInterval(labelTimer);fetchHealth();fetchTimer=setInterval(fetchHealth,FETCH_INTERVAL);labelTimer=setInterval(render,LABEL_INTERVAL);}
document.addEventListener('DOMContentLoaded',start);
document.addEventListener('DOMContentSwitch',function(){setTimeout(()=>{render();if(!snapshot)fetchHealth();},0);});
document.addEventListener('visibilitychange',function(){if(!document.hidden)fetchHealth();});
window.addEventListener('pageshow',fetchHealth);
window.addEventListener('focus',fetchHealth);
})();
