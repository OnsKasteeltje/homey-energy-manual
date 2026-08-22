(function(){
'use strict';
const BASE='/homey-energy-manual/data/';
const time=ts=>new Date(ts).toLocaleTimeString('nl-NL',{timeZone:'Europe/Amsterdam',hour:'2-digit',minute:'2-digit'});
const watts=n=>`${Math.round(Number(n)||0).toLocaleString('nl-NL')} W`;
const pv=s=>Math.max(0,(+s.solarEdgeW||0)+(+s.goodWe4200W||0)+(+s.goodWe2000W||0));
const home=s=>Math.max(0,pv(s)+(+s.p1W||0));
const residual=s=>Math.max(0,home(s)-Math.max(0,+s.boilerW||0)-Math.max(0,+s.teslaW||0));
let renderGeneration=0;
async function getJson(file){const r=await fetch(`${BASE}${file}?ts=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`${file}: ${r.status}`);return r.json();}
async function getSelectedDay(root){const date=root.dataset.selectedDayDate;const live=root.dataset.selectedDayLive==='true';if(live)return getJson('energy-day-v2.json');const roll=await getJson('energy-day-series-7d.json');return (roll.days||[]).find(d=>d&&d.date_local===date)||{date_local:date,samples:[]};}
function collect(samples){const out=[];let pbOn,pbHeat,pw,pd,pt,pHigh;for(const s of samples||[]){const bOn=!!s.boilerOn,bHeat=(+s.boilerW||0)>1500,w=!!s.washerActive,d=!!s.dryerActive,cs=String(s.chargeState||''),t=cs?cs==='plugged_in_charging':(+s.teslaW||0)>250,high=residual(s)>1500;if(pbOn!==undefined&&bOn!==pbOn)out.push({ts:s.ts,text:`Boiler ${bOn?'ingeschakeld':'uitgeschakeld'}`,kind:'boiler'});if(pbHeat!==undefined&&bHeat!==pbHeat)out.push({ts:s.ts,text:bHeat?`Boiler verwarmen gestart · ${watts(s.boilerW)}`:'Boiler verwarmen gestopt / op temperatuur',kind:'boiler'});if(pw!==undefined&&w!==pw)out.push({ts:s.ts,text:`Wasmachine ${w?'gestart':'klaar'}`,kind:'washer'});if(pd!==undefined&&d!==pd)out.push({ts:s.ts,text:`Droger ${d?'gestart':'klaar'}`,kind:'dryer'});if(pt!==undefined&&t!==pt)out.push({ts:s.ts,text:t?`Tesla laden gestart · ${watts(s.teslaW)}`:'Tesla laden gestopt',kind:'tesla'});if(pHigh!==undefined&&high!==pHigh)out.push({ts:s.ts,text:high?`Hoog niet-uitgesplitst verbruik gestart · ${watts(residual(s))}`:'Hoog niet-uitgesplitst verbruik geëindigd',kind:'other'});pbOn=bOn;pbHeat=bHeat;pw=w;pd=d;pt=t;pHigh=high;}return out.sort((a,b)=>new Date(a.ts)-new Date(b.ts));}
function panel(events,label){return `<div class="eh-panel eh-events-v2" data-activity-render="v2.8.57"><div class="eh-panel-title"><h3>Activiteit ${label}</h3><span class="eh-period">${events.length} gebeurtenissen</span></div><div class="eh-timeline">${events.length?events.map(e=>`<div class="eh-event" data-kind="${e.kind}"><span class="eh-time">${time(e.ts)}</span><span>${e.text}</span></div>`).join(''):'<div class="eh-empty">Geen herkenbare statusovergangen in deze dagreeks.</div>'}</div></div>`;}
function removeAllPanels(content){content.querySelectorAll('.eh-events-v2').forEach(node=>node.remove());}
async function enhance(){
  const generation=++renderGeneration;
  const root=document.getElementById('energy-history-dashboard');if(!root)return;
  const dayBtn=root.querySelector('.eh-tab[data-mode="day"]');if(!dayBtn||!dayBtn.classList.contains('is-active'))return;
  const content=root.querySelector('#eh-content');if(!content)return;
  removeAllPanels(content);
  try{
    const day=await getSelectedDay(root);
    if(generation!==renderGeneration||!root.isConnected||!content.isConnected)return;
    const label=root.dataset.selectedDayLive==='true'?'vandaag':new Date(`${day.date_local}T12:00:00`).toLocaleDateString('nl-NL',{weekday:'long',day:'numeric',month:'long'});
    removeAllPanels(content);
    content.insertAdjacentHTML('beforeend',panel(collect(day.samples||[]),label));
  }catch(e){
    if(generation!==renderGeneration||!root.isConnected||!content.isConnected)return;
    removeAllPanels(content);
    content.insertAdjacentHTML('beforeend',`<div class="eh-panel eh-events-v2" data-activity-render="v2.8.57"><div class="eh-empty">Activiteitstijdlijn kon niet worden geladen: ${e.message}</div></div>`);
  }
}
function schedule(){setTimeout(enhance,100);setTimeout(enhance,400);}
document.addEventListener('DOMContentLoaded',schedule);document.addEventListener('DOMContentSwitch',schedule);document.addEventListener('EnergyHistoryDayChanged',schedule);document.addEventListener('click',e=>{if(e.target.closest('#energy-history-dashboard .eh-tab'))schedule();});
})();
