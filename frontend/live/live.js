const STATE_URL='../../data/energy-state-v2.json';
const THRESHOLD=20;
const root=document.querySelector('#live-v2');
const freshness=document.querySelector('#freshness');
const finite=v=>v!==null&&v!==undefined&&Number.isFinite(Number(v));
const n=v=>finite(v)?Number(v):0, pos=v=>Math.max(0,n(v));
const fmt=v=>finite(v)?Math.round(Number(v)).toLocaleString('nl-NL')+' W':'—';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function normalize(raw){
  const pv=pos(raw?.pv?.total_w)||pos(raw?.pv?.solaredge_w)+pos(raw?.pv?.goodwe_4200_w)+pos(raw?.pv?.goodwe_2000_w);
  const grid=n(raw?.grid?.power_w), battery=n(raw?.battery?.power_w);
  const gate=raw?.balance?.control_gate?.derived_house_balance_valid ?? raw?.energy_budget?.derived_house_balance_valid;
  let house=null;
  if(gate!==false){
    if(finite(raw?.energy_budget?.house_load_w)) house=pos(raw.energy_budget.house_load_w);
    else if(finite(raw?.balance?.physical_house_candidate_w)&&Number(raw.balance.physical_house_candidate_w)>=0) house=pos(raw.balance.physical_house_candidate_w);
    else house=Math.max(0,pv+grid+Math.max(0,-battery)-Math.max(0,battery));
  }
  const load=(obj)=>finite(obj?.power_w)?pos(obj.power_w):null;
  const tesla=load(raw?.tesla), boiler=load({power_w:raw?.hot_water?.boiler_power_w}), quatt=load(raw?.quatt??raw?.heating);
  const washer=load(raw?.loads?.washer), dryer=load(raw?.loads?.dryer), quooker=load(raw?.loads?.quooker);
  const assigned=[tesla,boiler,quatt,washer,dryer,quooker].reduce((s,v)=>s+(v??0),0);
  const other=house===null?null:Math.max(0,house-assigned);
  return {raw,pv,grid,battery,house,tesla,boiler,quatt,washer,dryer,quooker,other,
    generated:raw?.meta?.generated_at,source:raw?.meta?.source_sample_at,revision:raw?.meta?.state_revision};
}
function card(title,value,sub,kind=''){
 return '<article class="card '+kind+'"><h3>'+esc(title)+'</h3><strong>'+fmt(value)+'</strong><small>'+esc(sub)+'</small></article>';
}
function device(title,value,sub){
 const active=finite(value)&&value>THRESHOLD;
 return '<article class="device '+(active?'active':'')+'"><span class="dot"></span><h3>'+esc(title)+'</h3><strong>'+fmt(value)+'</strong><small>'+esc(sub)+'</small></article>';
}
function render(s){
 const gridSub=s.grid<0?'export':s.grid>0?'import':'in balans';
 const batSub=s.battery>0?'laden':s.battery<0?'ontladen':'niet actief';
 const t=s.raw?.tesla||{}, hw=s.raw?.hot_water||{}, q=s.raw?.loads?.quooker||{};
 root.innerHTML='<div class="sources">'+
  card('PV Opwek',s.pv,'SolarEdge + GoodWe','pv')+
  card('Batterij',Math.abs(s.battery),batSub,'battery')+
  card('Net',Math.abs(s.grid),gridSub,'grid')+'</div>'+
  '<div class="flow"><div class="line"></div>'+card('Huis',s.house,'netto woningverbruik','house')+'</div>'+
  '<div class="devices">'+
  device('Tesla',s.tesla,s.tesla>THRESHOLD?'laden':t.connected?'aangesloten · geen actief verbruik':'niet aangesloten')+
  device('Boiler',s.boiler,s.boiler>THRESHOLD?'verwarmt':hw.boiler_on?'aan · laag/0 W':'uit')+
  device('Ruimteverwarming',s.quatt,s.quatt>THRESHOLD?'Quatt actief':'geen actief elektrisch verbruik')+
  device('Wasmachine',s.washer,s.washer>THRESHOLD?'actief':'niet actief / niet apart gemeten')+
  device('Droger',s.dryer,s.dryer>THRESHOLD?'actief':'niet actief / niet apart gemeten')+
  device('Quooker',s.quooker,s.quooker>THRESHOLD?'verwarmt':q.switch_on?'aan · idle':'uit')+
  device('Overig',s.other,s.other===null?'P1/PV niet tijdgelijk':'rest na bekende vermogens')+'</div>'+
  '<footer>Revision '+esc(s.revision??'?')+' · bron '+esc(s.source?new Date(s.source).toLocaleString('nl-NL',{timeZone:'Europe/Amsterdam'}):'onbekend')+'</footer>';
 const age=Date.now()-Date.parse(s.source||s.generated||'');
 const fresh=Number.isFinite(age)&&age<=15*60*1000;
 freshness.textContent=fresh?'● actueel':'● vertraagd';
 freshness.className='status '+(fresh?'ok':'stale');
}
async function load(){
 try{const r=await fetch(STATE_URL+'?v='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);render(normalize(await r.json()));}
 catch(e){root.innerHTML='<p class="error"><strong>Live state kon niet worden geladen.</strong><br>'+esc(e.message)+'</p>';freshness.textContent='● fout';freshness.className='status stale';}
}
load();setInterval(()=>{if(!document.hidden)load()},5*60*1000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)load()});