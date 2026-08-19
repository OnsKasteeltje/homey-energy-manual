(function(){
'use strict';
const BASE='/homey-energy-manual/data/';
const time=ts=>new Date(ts).toLocaleTimeString('nl-NL',{timeZone:'Europe/Amsterdam',hour:'2-digit',minute:'2-digit'});
const watts=n=>`${Math.round(Number(n)||0).toLocaleString('nl-NL')} W`;
const pv=s=>Math.max(0,(+s.solarEdgeW||0)+(+s.goodWe4200W||0)+(+s.goodWe2000W||0));
const home=s=>Math.max(0,pv(s)+(+s.p1W||0));
const residual=s=>Math.max(0,home(s)-Math.max(0,+s.boilerW||0)-Math.max(0,+s.teslaW||0));
async function getDay(){const r=await fetch(`${BASE}energy-day-v2.json?ts=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`energy-day-v2.json: ${r.status}`);return r.json();}
function collect(samples){
  const out=[];let pbOn,pbHeat,pw,pd,pt,pHigh;
  for(const s of samples||[]){
    const bOn=!!s.boilerOn,bHeat=(+s.boilerW||0)>1500,w=!!s.washerActive,d=!!s.dryerActive;
    const cs=String(s.chargeState||''),t=cs?cs==='plugged_in_charging':(+s.teslaW||0)>250;
    const high=residual(s)>1500;
    if(pbOn!==undefined&&bOn!==pbOn)out.push({ts:s.ts,text:`Boiler ${bOn?'ingeschakeld':'uitgeschakeld'}`,kind:'boiler'});
    if(pbHeat!==undefined&&bHeat!==pbHeat)out.push({ts:s.ts,text:bHeat?`Boiler verwarmen gestart · ${watts(s.boilerW)}`:'Boiler verwarmen gestopt / op temperatuur',kind:'boiler'});
    if(pw!==undefined&&w!==pw)out.push({ts:s.ts,text:`Wasmachine ${w?'gestart':'klaar'}`,kind:'washer'});
    if(pd!==undefined&&d!==pd)out.push({ts:s.ts,text:`Droger ${d?'gestart':'klaar'}`,kind:'dryer'});
    if(pt!==undefined&&t!==pt)out.push({ts:s.ts,text:t?`Tesla laden gestart · ${watts(s.teslaW)}`:'Tesla laden gestopt',kind:'tesla'});
    if(pHigh!==undefined&&high!==pHigh)out.push({ts:s.ts,text:high?`Hoog niet-uitgesplitst verbruik gestart · ${watts(residual(s))}`:'Hoog niet-uitgesplitst verbruik geëindigd',kind:'other'});
    pbOn=bOn;pbHeat=bHeat;pw=w;pd=d;pt=t;pHigh=high;
  }
  return out.sort((a,b)=>new Date(a.ts)-new Date(b.ts));
}
function panel(events){
  return `<div class="eh-panel eh-events-v2"><div class="eh-panel-title"><h3>Activiteit vandaag</h3><span class="eh-period">${events.length} gebeurtenissen</span></div><div class="eh-timeline">${events.length?events.map(e=>`<div class="eh-event" data-kind="${e.kind}"><span class="eh-time">${time(e.ts)}</span><span>${e.text}</span></div>`).join(''):'<div class="eh-empty">Nog geen herkenbare statusovergangen vandaag.</div>'}</div></div>`;
}
async function enhance(){
  const root=document.getElementById('energy-history-dashboard');if(!root)return;
  const dayBtn=root.querySelector('.eh-tab[data-mode="day"]');if(!dayBtn||!dayBtn.classList.contains('is-active'))return;
  const content=root.querySelector('#eh-content');if(!content||content.querySelector('.eh-events-v2'))return;
  try{const day=await getDay();content.insertAdjacentHTML('beforeend',panel(collect(day.samples||[])));}catch(e){content.insertAdjacentHTML('beforeend',`<div class="eh-panel eh-events-v2"><div class="eh-empty">Activiteitstijdlijn kon niet worden geladen: ${e.message}</div></div>`);}
}
function schedule(){setTimeout(enhance,80);setTimeout(enhance,350);setTimeout(enhance,900);}
document.addEventListener('DOMContentLoaded',schedule);document.addEventListener('DOMContentSwitch',schedule);document.addEventListener('click',e=>{if(e.target.closest('#energy-history-dashboard .eh-tab'))schedule();});
})();
