(function(){
'use strict';
const BASE='/homey-energy-manual/data/';
const fmt=(n,d=1)=>Number(n||0).toLocaleString('nl-NL',{minimumFractionDigits:d,maximumFractionDigits:d});
const iso=d=>{const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),day=String(d.getDate()).padStart(2,'0');return `${y}-${m}-${day}`;};
const dayLabel=d=>d.toLocaleDateString('nl-NL',{weekday:'short',day:'numeric'}).replace('.','');
const path=(vals,W,H,p,max)=>vals.map((v,i)=>{const x=p+(W-2*p)*i/6;if(v==null)return null;const y=p+(H-2*p)*(1-v/max);return{x,y,i};}).filter(Boolean).map((q,j,a)=>`${j===0||q.i!==a[j-1].i+1?'M':'L'}${q.x.toFixed(1)},${q.y.toFixed(1)}`).join(' ');
async function rollingWeek(){
 const content=document.querySelector('#eh-content');if(!content)return;
 const r=await fetch(`${BASE}energy-daily-history.json?ts=${Date.now()}`,{cache:'no-store'});if(!r.ok)return;
 const hist=await r.json(),byDate=new Map((hist.days||[]).map(d=>[d.date,d]));
 const today=new Date(),slots=[];for(let i=6;i>=0;i--){const d=new Date(today);d.setHours(12,0,0,0);d.setDate(today.getDate()-i);slots.push({date:iso(d),label:dayLabel(d),data:byDate.get(iso(d))||null});}
 const defs=[['Netimport','eh-import','p1_import_kWh_est'],['Netexport','eh-export','p1_export_kWh_est'],['Boiler','eh-home','boiler_kWh_est'],['Tesla','eh-pv','tesla_kWh_est']];
 const series=defs.map(([label,cls,key])=>({label,cls,values:slots.map(s=>s.data?Number(s.data[key]||0):null)}));
 const available=slots.filter(s=>s.data).length,W=1100,H=330,p=48,nums=series.flatMap(s=>s.values.filter(v=>v!=null)),max=Math.max(1,...nums),sum=key=>slots.reduce((a,s)=>a+(s.data?Number(s.data[key]||0):0),0);
 let g='';for(let i=0;i<=5;i++){const y=p+(H-2*p)*i/5,v=max*(1-i/5);g+=`<line x1="${p}" x2="${W-p}" y1="${y}" y2="${y}" class="eh-gridline"/><text x="${p-8}" y="${y+4}" text-anchor="end" class="eh-axis-label">${fmt(v)} kWh</text>`;}
 series.forEach(s=>{const d=path(s.values,W,H,p,max);if(d)g+=`<path d="${d}" class="eh-line ${s.cls}"/>`;});
 slots.forEach((s,i)=>{const x=p+(W-2*p)*i/6;g+=`<text x="${x}" y="${H-10}" text-anchor="middle" class="eh-axis-label">${s.label}</text>`;});
 const cards=[['Netimport',sum('p1_import_kWh_est')],['Netexport',sum('p1_export_kWh_est')],['Boiler',sum('boiler_kWh_est')],['Tesla',sum('tesla_kWh_est')]].map(x=>`<div class="eh-card"><div class="eh-card-label">${x[0]}</div><div class="eh-card-value">${fmt(x[1])} kWh</div></div>`).join('')+`<div class="eh-card"><div class="eh-card-label">PV-productie</div><div class="eh-card-value">—</div><div class="eh-card-sub">nog niet historisch opgeslagen</div></div>`;
 const legend=`<div class="eh-legend"><span class="eh-key imp">Netimport</span><span class="eh-key exp">Netexport</span><span class="eh-key home">Boiler</span><span class="eh-key pv">Tesla</span></div>`;
 content.innerHTML=`<div class="eh-cards">${cards}</div><div class="eh-panel"><div class="eh-panel-title"><h3>Weekoverzicht</h3><span class="eh-warning">${available} van 7 dagen beschikbaar</span></div><div class="eh-chart-wrap"><div class="eh-chart-interactive eh-rolling-week"><svg viewBox="0 0 ${W} ${H}" class="eh-chart">${g}<line class="eh-hover-line" x1="0" x2="0" y1="${p}" y2="${H-p}"/></svg><div class="eh-tooltip" role="status"></div></div></div>${legend}</div>`;
 const box=content.querySelector('.eh-rolling-week'),svg=box.querySelector('svg'),tip=box.querySelector('.eh-tooltip'),line=box.querySelector('.eh-hover-line');
 const update=xClient=>{const rect=svg.getBoundingClientRect(),xSvg=(xClient-rect.left)/rect.width*W,idx=Math.max(0,Math.min(6,Math.round((xSvg-p)/(W-2*p)*6))),x=p+(W-2*p)*idx/6,s=slots[idx];line.setAttribute('x1',x);line.setAttribute('x2',x);line.classList.add('is-visible');const rows=series.map(q=>`<div class="eh-tooltip-row"><span class="eh-tooltip-key ${q.cls.replace('eh-','')}">${q.label}</span><strong>${q.values[idx]==null?'geen data':fmt(q.values[idx])+' kWh'}</strong></div>`).join('');tip.innerHTML=`<div class="eh-tooltip-title">${s.label} · ${s.date}</div>${rows}`;tip.classList.add('is-visible');const px=x/W*rect.width,tw=Math.min(250,box.clientWidth-16);tip.style.width=`${tw}px`;tip.style.left=`${Math.max(8,Math.min(box.clientWidth-tw-8,px+12))}px`;tip.style.top='8px';};
 box.addEventListener('mousemove',e=>update(e.clientX));box.addEventListener('mouseleave',()=>{line.classList.remove('is-visible');tip.classList.remove('is-visible');});box.addEventListener('touchstart',e=>e.touches[0]&&update(e.touches[0].clientX),{passive:true});box.addEventListener('touchmove',e=>e.touches[0]&&update(e.touches[0].clientX),{passive:true});
}
document.addEventListener('click',e=>{const b=e.target.closest('.eh-tab[data-mode="week"]');if(b)setTimeout(()=>rollingWeek().catch(()=>{}),50);});
document.addEventListener('DOMContentSwitch',()=>{const b=document.querySelector('.eh-tab[data-mode="week"].is-active');if(b)setTimeout(()=>rollingWeek().catch(()=>{}),80);});
})();
