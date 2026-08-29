# Homey Load Map

Deze pagina visualiseert de Homey-belasting over één uur. Het doel is niet alleen te tonen **welke flows draaien**, maar vooral **wanneer wake-ups samenvallen** en waar device/API-calls of fysieke writes zich opstapelen. Dit ondersteunt de structurele analyse van Homey-throttling.

<div id="homey-load-map" class="hlm-root">
  <div class="hlm-summary">
    <div class="hlm-stat"><span>Runs / uur</span><strong id="hlm-total-runs">—</strong></div>
    <div class="hlm-stat"><span>Zware wake-ups</span><strong id="hlm-heavy-runs">—</strong></div>
    <div class="hlm-stat"><span>Drukste minuut</span><strong id="hlm-peak-minute">—</strong></div>
  </div>

  <div class="hlm-legend" aria-label="Legenda">
    <span><i class="hlm-dot hlm-light"></i>Licht: in-memory/logica</span>
    <span><i class="hlm-dot hlm-medium"></i>Middel: logic/state I/O</span>
    <span><i class="hlm-dot hlm-heavy"></i>Zwaar: device/API scan</span>
    <span><i class="hlm-dot hlm-write"></i>Actuator-write</span>
  </div>

  <div class="hlm-panel hlm-scroll"><svg id="hlm-timeline" viewBox="0 0 980 360" role="img" aria-label="Tijdslijn van Homey triggers over zestig minuten"></svg></div>

  <div class="hlm-panel">
    <div class="hlm-panel-head"><div><h2>Cumulatieve load per minuut</h2><p>Piekkolommen wijzen op gelijktijdige wake-ups.</p></div><label class="hlm-switch"><input id="hlm-stagger-publisher" type="checkbox"> Simuleer Publisher +2 min</label></div>
    <div class="hlm-scroll"><svg id="hlm-load-chart" viewBox="0 0 980 190" role="img" aria-label="Cumulatieve Homey-load per minuut met relatieve loadpunten op de verticale as"></svg></div>
    <p class="hlm-chart-help"><strong>Zo lees je deze grafiek:</strong> de horizontale as is de minuut binnen het uur. De verticale as is de som van de relatieve loadgewichten van alle flows die in die minuut wakker worden. Een hogere kolom betekent dus niet automatisch meer CPU-verbruik, maar wel een grotere kans dat meerdere of zwaardere Homey-acties tegelijk plaatsvinden. Voorbeeld: Tesla writer (1) + Energy Core (3) + Decision (1) + Publisher (2) in dezelfde minuut geeft een relatieve load van <strong>7</strong>.</p>
  </div>

  <div class="hlm-panel">
    <div class="hlm-panel-head"><div><h2>Schema-vergelijking</h2><p>Vergelijk het huidige schema met de simulatie. Lager is beter voor piek en actieve minuten; lagere variantie betekent gelijkmatiger belasting.</p></div><strong id="hlm-verdict" class="hlm-verdict">—</strong></div>
    <div class="hlm-compare">
      <div class="hlm-compare-head">Maatstaf</div><div class="hlm-compare-head">Huidig</div><div class="hlm-compare-head">Simulatie</div>
      <div>Piekbelasting</div><strong id="hlm-base-peak">—</strong><strong id="hlm-sim-peak">—</strong>
      <div>Actieve minuten</div><strong id="hlm-base-active">—</strong><strong id="hlm-sim-active">—</strong>
      <div>Load-variantie</div><strong id="hlm-base-var">—</strong><strong id="hlm-sim-var">—</strong>
    </div>
    <p id="hlm-verdict-text" class="hlm-verdict-text"></p>
  </div>

  <div class="hlm-notes"><div><h3>Bevestigde baseline</h3><ul><li>Energy Core v2: iedere 5 minuten.</li><li>Tesla / Easee writer: iedere 1 minuut.</li><li>Publisher: iedere 15 minuten, publication-only.</li><li>Website: geen Homey-devicepolling.</li></ul></div><div><h3>Volgende stap</h3><p>Planner, State/Decision fan-out, warm water, Quooker, history, PBTH/prijs en overige actieve flows worden toegevoegd zodra hun actuele trigger/cadans in de Load Map is bevestigd.</p></div></div>
</div>

<style>
.hlm-root{--hlm-light:#53b760;--hlm-medium:#f07f36;--hlm-heavy:#8255e9;--hlm-write:#df6f63;--hlm-border:rgba(127,127,127,.28);display:grid;gap:1.1rem;margin-top:1rem}.hlm-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.75rem}.hlm-stat,.hlm-panel,.hlm-notes>div{border:1px solid var(--hlm-border);border-radius:14px;padding:1rem;background:var(--md-default-bg-color)}.hlm-stat span{display:block;font-size:.75rem;color:var(--md-default-fg-color--light)}.hlm-stat strong{display:block;font-size:1.8rem;margin-top:.15rem}.hlm-legend{display:flex;flex-wrap:wrap;gap:.6rem}.hlm-legend span{display:inline-flex;align-items:center;gap:.45rem;border:1px solid var(--hlm-border);border-radius:9px;padding:.45rem .7rem}.hlm-dot{width:.8rem;height:.8rem;border-radius:50%;display:inline-block}.hlm-light{background:var(--hlm-light)}.hlm-medium{background:var(--hlm-medium)}.hlm-heavy{background:var(--hlm-heavy)}.hlm-write{background:var(--hlm-write)}.hlm-scroll{overflow-x:auto}.hlm-scroll svg{display:block;min-width:820px;width:100%;height:auto}.hlm-panel-head{display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}.hlm-panel-head h2{margin:0;font-size:1.25rem}.hlm-panel-head p{margin:.25rem 0 0;color:var(--md-default-fg-color--light)}.hlm-switch{display:flex;align-items:center;gap:.55rem;white-space:nowrap}.hlm-switch input{width:1.2rem;height:1.2rem}.hlm-chart-help{margin:.7rem 0 0;color:var(--md-default-fg-color--light);font-size:.9rem;line-height:1.5}.hlm-notes{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}.hlm-notes h3{margin-top:0}.hlm-notes p,.hlm-notes ul{margin-bottom:0}.hlm-root svg text{font-family:var(--md-text-font-family);fill:var(--md-default-fg-color)}.hlm-compare{display:grid;grid-template-columns:minmax(140px,1.4fr) 1fr 1fr;gap:.5rem 1rem;margin-top:1rem;align-items:center}.hlm-compare-head{font-size:.75rem;color:var(--md-default-fg-color--light);font-weight:700}.hlm-verdict{border:1px solid var(--hlm-border);border-radius:999px;padding:.35rem .7rem;font-size:.85rem}.hlm-verdict.good{color:#238636;border-color:#238636}.hlm-verdict.bad{color:#cf222e;border-color:#cf222e}.hlm-verdict.equal{color:var(--md-default-fg-color--light)}.hlm-verdict-text{margin:.8rem 0 0;color:var(--md-default-fg-color--light)}@media(max-width:700px){.hlm-summary,.hlm-notes{grid-template-columns:1fr}.hlm-compare{grid-template-columns:1.2fr 1fr 1fr;font-size:.85rem}}
</style>

<script>
(function(){
 const root=document.getElementById('homey-load-map');if(!root||root.dataset.ready)return;root.dataset.ready='1';
 const colors={light:'#53b760',medium:'#f07f36',heavy:'#8255e9',write:'#df6f63'};
 const flows=[{name:'Tesla / Easee writer',interval:1,offset:0,weight:1,kind:'write'},{name:'Energy Core v2',interval:5,offset:0,weight:3,kind:'heavy'},{name:'Decision / downstream',interval:5,offset:0,weight:1,kind:'light'},{name:'Publisher',interval:15,offset:0,weight:2,kind:'medium'}];
 const ns='http://www.w3.org/2000/svg';function el(n,a){const x=document.createElementNS(ns,n);Object.entries(a||{}).forEach(([k,v])=>x.setAttribute(k,v));return x}function txt(s,x,y,v,a){const n=el('text',Object.assign({x,y,'font-size':'12'},a||{}));n.textContent=v;s.appendChild(n)}function events(f){const a=[];for(let m=f.offset;m<60;m+=f.interval)a.push(m);return a}
 function loads(active){const l=Array(60).fill(0);active.forEach(f=>events(f).forEach(m=>l[m]+=f.weight));return l}function metrics(l){const mean=l.reduce((a,b)=>a+b,0)/60;return{peak:Math.max(...l),active:l.filter(v=>v>0).length,variance:l.reduce((a,v)=>a+(v-mean)*(v-mean),0)/60}}
 const baseline=flows.map(f=>Object.assign({},f)),simulated=flows.map(f=>Object.assign({},f,{offset:f.name==='Publisher'?2:f.offset}));const bm=metrics(loads(baseline)),sm=metrics(loads(simulated));
 function render(){const stagger=document.getElementById('hlm-stagger-publisher').checked,active=stagger?simulated:baseline,tl=document.getElementById('hlm-timeline'),lc=document.getElementById('hlm-load-chart');tl.replaceChildren();lc.replaceChildren();const border='rgba(127,127,127,.30)',muted='rgba(127,127,127,.95)',left=185,right=950,width=right-left;for(let m=0;m<=60;m+=5){const x=left+width*m/60;tl.appendChild(el('line',{x1:x,y1:32,x2:x,y2:330,stroke:border,'stroke-width':m%15===0?1.6:.8,'stroke-dasharray':m%15===0?'0':'3 4'}));txt(tl,x,22,String(m).padStart(2,'0'),{'text-anchor':'middle',fill:muted})}active.forEach((f,i)=>{const y=62+i*65;txt(tl,8,y+4,f.name,{'font-size':'13','font-weight':'700'});tl.appendChild(el('line',{x1:left,y1:y,x2:right,y2:y,stroke:border}));events(f).forEach(m=>{const x=left+width*m/60;tl.appendChild(el('circle',{cx:x,cy:y,r:f.kind==='write'?4.4:5.5,fill:colors[f.kind],stroke:'rgba(60,60,60,.75)','stroke-width':'.5'}))});txt(tl,8,y+22,'elke '+f.interval+' min · gewicht '+f.weight,{'font-size':'11',fill:muted})});txt(tl,left,350,'minuten →',{fill:muted});const load=loads(active);let total=0,heavy=0;active.forEach(f=>events(f).forEach(()=>{total++;if(f.kind==='heavy')heavy++}));const max=Math.max(...load,1),peak=load.indexOf(max);document.getElementById('hlm-total-runs').textContent=total;document.getElementById('hlm-heavy-runs').textContent=heavy;document.getElementById('hlm-peak-minute').textContent=':'+String(peak).padStart(2,'0')+' ('+max+')';const cl=54,cr=958,cw=cr-cl,top=20,by=148,ch=118;
 lc.appendChild(el('line',{x1:cl,y1:top,x2:cl,y2:by,stroke:border}));lc.appendChild(el('line',{x1:cl,y1:by,x2:cr,y2:by,stroke:border}));
 const tickStep=max<=5?1:Math.ceil(max/5);for(let v=0;v<=max;v+=tickStep){const y=by-ch*v/max;lc.appendChild(el('line',{x1:cl,y1:y,x2:cr,y2:y,stroke:border,'stroke-width':v===0?1:.7,'stroke-dasharray':v===0?'0':'3 4'}));txt(lc,44,y+4,String(v),{'text-anchor':'end','font-size':'10',fill:muted})}if(max%tickStep!==0){const y=by-ch;lc.appendChild(el('line',{x1:cl,y1:y,x2:cr,y2:y,stroke:border,'stroke-width':'.7','stroke-dasharray':'3 4'}));txt(lc,44,y+4,String(max),{'text-anchor':'end','font-size':'10',fill:muted})}
 load.forEach((v,m)=>{const bw=cw/60-2,x=cl+cw*m/60+1,h=ch*v/max;lc.appendChild(el('rect',{x,y:by-h,width:bw,height:h,rx:1.5,fill:v===max?colors.heavy:colors.medium,opacity:v===0?.2:.85}))});for(let m=0;m<=60;m+=5){const x=cl+cw*m/60;txt(lc,x,168,String(m),{'text-anchor':'middle','font-size':'10',fill:muted})}txt(lc,cl,185,'minuut →',{'font-size':'10',fill:muted});txt(lc,8,14,'relatieve loadpunten',{'font-size':'10',fill:muted})}
 document.getElementById('hlm-base-peak').textContent=bm.peak.toFixed(1);document.getElementById('hlm-sim-peak').textContent=sm.peak.toFixed(1);document.getElementById('hlm-base-active').textContent=bm.active;document.getElementById('hlm-sim-active').textContent=sm.active;document.getElementById('hlm-base-var').textContent=bm.variance.toFixed(2);document.getElementById('hlm-sim-var').textContent=sm.variance.toFixed(2);
 const score=(sm.peak-bm.peak)*10+(sm.active-bm.active)+(sm.variance-bm.variance);const verdict=document.getElementById('hlm-verdict'),vt=document.getElementById('hlm-verdict-text');if(score<-.01){verdict.textContent='BETER';verdict.className='hlm-verdict good';vt.textContent='De simulatie verlaagt de samengestelde load-score ten opzichte van het huidige schema.'}else if(score>.01){verdict.textContent='SLECHTER';verdict.className='hlm-verdict bad';vt.textContent='Niet toepassen: de simulatie verbetert de piek niet voldoende en/of creëert extra actieve minuten of een ongunstiger load-profiel.'}else{verdict.textContent='GELIJK';verdict.className='hlm-verdict equal';vt.textContent='De simulatie levert met deze maatstaven geen betekenisvolle verbetering op.'}
 document.getElementById('hlm-stagger-publisher').addEventListener('change',render);render();
})();
</script>

!!! note "Interpretatie"
    De gewichten zijn relatieve diagnosegewichten, geen gemeten Athom/Homey CPU-percentages. De automatische **BETER / GELIJK / SLECHTER**-beoordeling is daarom een planningshulpmiddel: eerst peak load, daarna actieve minuten en load-variantie. Een simulatie verandert niets op Homey zelf.
