(function(){
  'use strict';
  const BASE='/homey-energy-manual/data/';
  const $=s=>document.querySelector(s);
  const fmt=(n,d=1)=>Number(n||0).toLocaleString('nl-NL',{minimumFractionDigits:d,maximumFractionDigits:d});
  const kwh=n=>`${fmt(n)} kWh`;
  const get=async f=>{const r=await fetch(`${BASE}${f}?ts=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: ${r.status}`);return r.json();};
  const integrate=(samples,keyFn)=>{let e=0;for(let i=1;i<samples.length;i++){const a=samples[i-1],b=samples[i],dt=Math.min(10*60*1000,new Date(b.ts)-new Date(a.ts))/3600000;if(dt<=0)continue;e+=(keyFn(a)+keyFn(b))/2*dt/1000;}return Math.max(0,e);};
  const enc=o=>encodeURIComponent(JSON.stringify(o));
  const dec=s=>JSON.parse(decodeURIComponent(s));
  function path(vals,W,H,p,ymin,ymax){if(vals.length<2)return'';return vals.map((v,i)=>{const x=p+(W-2*p)*i/(vals.length-1),y=p+(H-2*p)*(1-(v-ymin)/(ymax-ymin||1));return`${i?'L':'M'}${x.toFixed(1)},${y.toFixed(1)}`}).join(' ');}
  function chart(series,labels,opts={}){
    const W=1100,H=330,p=48,all=series.flatMap(s=>s.values),signed=opts.signed===true,max=Math.max(1,...all.map(Math.abs)),ymin=signed?-max:0,ymax=max,unit=opts.unit||'kWh',scale=opts.scale||1;
    let g='';
    for(let i=0;i<=5;i++){
      const y=p+(H-2*p)*i/5;
      g+=`<line x1="${p}" x2="${W-p}" y1="${y}" y2="${y}" class="eh-gridline"/>`;
      const v=(ymax-(ymax-ymin)*i/5)/scale;
      g+=`<text x="${p-8}" y="${y+4}" text-anchor="end" class="eh-axis-label">${fmt(v,unit==='W'?0:1)} ${unit}</text>`;
    }
    if(signed){const zy=p+(H-2*p)*(1-(0-ymin)/(ymax-ymin));g+=`<line x1="${p}" x2="${W-p}" y1="${zy}" y2="${zy}" class="eh-zero"/>`;}
    series.forEach(s=>{const d=path(s.values,W,H,p,ymin,ymax);if(d)g+=`<path d="${d}" class="eh-line ${s.cls}"/>`;});
    for(let i=0;i<Math.min(5,labels.length||0);i++){
      const count=Math.min(5,labels.length),x=p+(W-2*p)*(labels.length<=1?0:i/(count-1||1)),idx=labels.length<=1?0:Math.round((labels.length-1)*i/(count-1||1));
      g+=`<text x="${x}" y="${H-10}" text-anchor="middle" class="eh-axis-label">${labels[idx]||''}</text>`;
    }
    const meta=series.map(s=>({label:s.label||'',cls:s.cls,values:s.values,abs:s.abs===true}));
    return `<div class="eh-chart-interactive" data-labels="${enc(labels)}" data-series="${enc(meta)}" data-unit="${unit}" data-scale="${scale}" data-w="${W}" data-pad="${p}"><svg viewBox="0 0 ${W} ${H}" class="eh-chart">${g}<line class="eh-hover-line" x1="0" x2="0" y1="${p}" y2="${H-p}"/><circle class="eh-hover-dot" cx="0" cy="0" r="5"/></svg><div class="eh-tooltip" role="status" aria-live="polite"></div></div>`;
  }
  function bindChartInteractions(root=document){
    root.querySelectorAll('.eh-chart-interactive').forEach(box=>{
      if(box.dataset.bound==='1')return;box.dataset.bound='1';
      const svg=box.querySelector('svg'),tip=box.querySelector('.eh-tooltip'),line=box.querySelector('.eh-hover-line'),dot=box.querySelector('.eh-hover-dot'),labels=dec(box.dataset.labels),series=dec(box.dataset.series),W=+box.dataset.w,p=+box.dataset.pad,unit=box.dataset.unit,scale=+box.dataset.scale||1;
      const update=clientX=>{
        if(!labels.length)return;
        const r=svg.getBoundingClientRect(),xSvg=(clientX-r.left)/r.width*W,usable=W-2*p,ratio=Math.max(0,Math.min(1,(xSvg-p)/usable)),idx=Math.round(ratio*(labels.length-1)),x=p+usable*(labels.length<=1?0:idx/(labels.length-1));
        line.setAttribute('x1',x);line.setAttribute('x2',x);line.classList.add('is-visible');
        const rows=series.map(s=>{const raw=Number(s.values[idx]||0),shown=(s.abs?Math.abs(raw):raw)/scale;return `<div class="eh-tooltip-row"><span class="eh-tooltip-key ${s.cls.replace('eh-','')}">${s.label}</span><strong>${fmt(shown,unit==='W'?0:1)} ${unit}</strong></div>`;}).join('');
        tip.innerHTML=`<div class="eh-tooltip-title">${labels[idx]}</div>${rows}`;tip.classList.add('is-visible');
        const px=(x/W)*r.width,tipW=Math.min(250,box.clientWidth-16),left=Math.max(8,Math.min(box.clientWidth-tipW-8,px+12));tip.style.left=`${left}px`;tip.style.width=`${tipW}px`;tip.style.top='8px';
        if(series.length){const vals=series.map(s=>Number(s.values[idx]||0)),all=series.flatMap(s=>s.values.map(Number)),max=Math.max(1,...all.map(Math.abs)),ymin=all.some(v=>v<0)?-max:0,ymax=max,first=vals[0],H=330,y=p+(H-2*p)*(1-(first-ymin)/(ymax-ymin||1));dot.setAttribute('cx',x);dot.setAttribute('cy',y);dot.classList.add('is-visible');}
      };
      const hide=()=>{line.classList.remove('is-visible');dot.classList.remove('is-visible');tip.classList.remove('is-visible');};
      box.addEventListener('mousemove',e=>update(e.clientX));
      box.addEventListener('mouseleave',hide);
      box.addEventListener('touchstart',e=>{if(e.touches[0])update(e.touches[0].clientX);},{passive:true});
      box.addEventListener('touchmove',e=>{if(e.touches[0])update(e.touches[0].clientX);},{passive:true});
      box.addEventListener('touchend',()=>setTimeout(hide,1200),{passive:true});
    });
  }
  function legend(items){return `<div class="eh-legend">${items.map(([cls,label])=>`<span class="eh-key ${cls}">${label}</span>`).join('')}</div>`;}
  function cards(v){return `<div class="eh-cards">${[['PV-productie',kwh(v.pv)],['Verbruik woning',kwh(v.home)],['Netimport',kwh(v.imp)],['Netexport',kwh(v.exp)],['Eigen PV',`${fmt(v.selfPct,0)}%`,`${kwh(v.self)} direct`],['Accu geladen',kwh(0),'nog geen opslagmeting'],['Accu ontladen',kwh(0),'nog geen opslagmeting']].map(x=>`<div class="eh-card"><div class="eh-card-label">${x[0]}</div><div class="eh-card-value">${x[1]}</div>${x[2]?`<div class="eh-card-sub">${x[2]}</div>`:''}</div>`).join('')}</div>`;}
  function simpleCards(items){return `<div class="eh-cards">${items.map(x=>`<div class="eh-card"><div class="eh-card-label">${x[0]}</div><div class="eh-card-value">${x[1]}</div>${x[2]?`<div class="eh-card-sub">${x[2]}</div>`:''}</div>`).join('')}</div>`;}
  function events(ps){const out=[];let pw,pd,pb,pt;for(const s of ps){const t=new Date(s.ts).toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'});if(typeof s.washerActive==='boolean'&&s.washerActive!==pw){if(pw!==undefined)out.push({t,text:`Wasmachine ${s.washerActive?'gestart':'klaar'}`});pw=s.washerActive;}if(typeof s.dryerActive==='boolean'&&s.dryerActive!==pd){if(pd!==undefined)out.push({t,text:`Droger ${s.dryerActive?'gestart':'klaar'}`});pd=s.dryerActive;}const bo=Number(s.boilerW||0)>300;if(bo!==pb){if(pb!==undefined)out.push({t,text:`Boiler ${bo?'verwarmen gestart':'verwarmen gestopt'}`});pb=bo;}const charging=String(s.chargeState||'').includes('charging')||Number(s.teslaW||0)>250;if(charging!==pt){if(pt!==undefined)out.push({t,text:`Tesla laden ${charging?'gestart':'gestopt'}`});pt=charging;}}return out.slice(-12);}
  function dayView(day){
    const ps=day.samples||[];if(!ps.length)return '<div class="eh-empty">Energy Core v2-daghistorie is gestart; het eerste meetpunt wordt opgebouwd.</div>';
    const norm=ps.map(s=>{const pv=Math.max(0,(+s.solarEdgeW||0)+(+s.goodWe4200W||0)+(+s.goodWe2000W||0)),p1=+s.p1W||0,home=Math.max(0,pv+p1),imp=Math.max(0,p1),exportW=Math.max(0,-p1),selfW=Math.max(0,pv-exportW);return{...s,pv,home,imp,exp:-exportW,selfW};});
    const enough=norm.length>=2,pv=enough?integrate(norm,s=>s.pv):0,home=enough?integrate(norm,s=>s.home):0,imp=enough?integrate(norm,s=>s.imp):0,exp=enough?integrate(norm,s=>-s.exp):0,self=enough?integrate(norm,s=>s.selfW):0,selfPct=pv?100*Math.min(pv,self)/pv:0,labels=norm.map(s=>new Date(s.ts).toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'})),ev=events(norm),held=norm.filter(s=>s.held).length,last=norm.at(-1);
    const current=`<div class="eh-panel"><div class="eh-panel-title"><h3>Actueel meetpunt</h3><span class="eh-period">revision ${last.revision??'?'}${last.held?' · hold-last-value':''}</span></div><div class="eh-cards"><div class="eh-card"><div class="eh-card-label">PV nu</div><div class="eh-card-value">${Math.round(last.pv)} W</div></div><div class="eh-card"><div class="eh-card-label">Woning nu</div><div class="eh-card-value">${Math.round(last.home)} W</div></div><div class="eh-card"><div class="eh-card-label">Net nu</div><div class="eh-card-value">${Math.round(Math.abs(+last.p1W||0))} W</div><div class="eh-card-sub">${(+last.p1W||0)>=0?'import':'export'}</div></div></div></div>`;
    if(!enough)return `${current}<div class="eh-empty">Eerste v2-historypunt staat klaar. Vanaf het volgende 5-minutenpunt worden daggrafiek en kWh-integralen berekend.</div>`;
    const ch=chart([{values:norm.map(s=>s.pv),cls:'eh-pv',label:'PV-productie'},{values:norm.map(s=>s.home),cls:'eh-home',label:'Verbruik woning'},{values:norm.map(s=>s.imp),cls:'eh-import',label:'Netimport'},{values:norm.map(s=>s.exp),cls:'eh-export',label:'Netexport',abs:true},{values:norm.map(()=>0),cls:'eh-battery',label:'Accu'}],labels,{signed:true,unit:'W',scale:1});
    return `${cards({pv,home,imp,exp,self,selfPct})}<div class="eh-panel"><div class="eh-panel-title"><h3>Energie-overzicht · vandaag</h3><span class="eh-period">${norm.length} v2-punten · ${held} hold-punten</span></div><div class="eh-chart-wrap">${ch}</div>${legend([['pv','PV-productie'],['home','Verbruik woning'],['imp','Netimport'],['exp','Netexport'],['bat','Accu']])}</div><div class="eh-bottom"><div class="eh-panel"><h3>Energiebalans</h3><div class="eh-balance"><div><div class="eh-bnode">☀️ PV<br><strong>${kwh(pv)}</strong></div><div class="eh-bnode" style="margin-top:8px">🌐 Netimport<br><strong>${kwh(imp)}</strong></div></div><div class="eh-arrow">→</div><div><div class="eh-bnode">🏠 Woning<br><strong>${kwh(home)}</strong></div><div class="eh-bnode" style="margin-top:8px">↗ Netexport<br><strong>${kwh(exp)}</strong></div></div></div></div><div class="eh-panel"><h3>Activiteitstijdlijn</h3><div class="eh-timeline">${ev.length?ev.map(e=>`<div class="eh-event"><span class="eh-time">${e.t}</span><span>${e.text}</span></div>`).join(''):'<div class="eh-empty">Nog geen statusovergangen sinds start van v2-daghistorie.</div>'}</div></div></div><div class="eh-foot">Beweeg met de muis over de grafiek of tik op mobiel om tijdstip en waarden te zien.</div>`;
  }
  function aggView(hist,mode){
    const days=(hist.days||[]).slice().sort((a,b)=>a.date.localeCompare(b.date)),n=mode==='week'?7:31,sel=days.slice(-n),labels=sel.map(d=>mode==='week'?d.date.slice(5):d.date.slice(8)),imp=sel.map(d=>(+d.p1_import_kWh_est||0)),exp=sel.map(d=>(+d.p1_export_kWh_est||0)),bo=sel.map(d=>(+d.boiler_kWh_est||0)),tes=sel.map(d=>(+d.tesla_kWh_est||0)),sum=k=>sel.reduce((a,d)=>a+(+d[k]||0),0),availability=mode==='week'?`${sel.length} van 7 dagen beschikbaar`:`${sel.length} historische dagen beschikbaar`;
    const ch=chart([{values:imp,cls:'eh-import',label:'Netimport'},{values:exp,cls:'eh-export',label:'Netexport'},{values:bo,cls:'eh-home',label:'Boiler'},{values:tes,cls:'eh-pv',label:'Tesla'}],labels,{unit:'kWh',scale:1});
    return `${simpleCards([['Netimport',kwh(sum('p1_import_kWh_est'))],['Netexport',kwh(sum('p1_export_kWh_est'))],['Boiler',kwh(sum('boiler_kWh_est'))],['Tesla',kwh(sum('tesla_kWh_est'))],['PV-productie','—','nog niet historisch opgeslagen']])}<div class="eh-panel"><div class="eh-panel-title"><h3>${mode==='week'?'Week':'Maand'}overzicht</h3><span class="eh-warning">${availability}</span></div>${sel.length?`<div class="eh-chart-wrap">${ch}</div>${legend([['imp','Netimport'],['exp','Netexport'],['home','Boiler'],['pv','Tesla']])}`:'<div class="eh-empty">Nog geen daghistorie beschikbaar.</div>'}</div>`;
  }
  function yearView(hist){
    const days=(hist.days||[]).slice().sort((a,b)=>a.date.localeCompare(b.date));if(!days.length)return '<div class="eh-empty">Nog geen daghistorie beschikbaar voor een jaaroverzicht.</div>';
    const year=days.at(-1).date.slice(0,4),sel=days.filter(d=>d.date.startsWith(year+'-')),months=Array.from({length:12},()=>({imp:0,exp:0,bo:0,tes:0,days:0}));
    for(const d of sel){const m=months[+d.date.slice(5,7)-1];if(!m)continue;m.imp+=+d.p1_import_kWh_est||0;m.exp+=+d.p1_export_kWh_est||0;m.bo+=+d.boiler_kWh_est||0;m.tes+=+d.tesla_kWh_est||0;m.days++;}
    const labels=['Jan','Feb','Mrt','Apr','Mei','Jun','Jul','Aug','Sep','Okt','Nov','Dec'],ch=chart([{values:months.map(m=>m.imp),cls:'eh-import',label:'Netimport'},{values:months.map(m=>m.exp),cls:'eh-export',label:'Netexport'},{values:months.map(m=>m.bo),cls:'eh-home',label:'Boiler'},{values:months.map(m=>m.tes),cls:'eh-pv',label:'Tesla'}],labels,{unit:'kWh',scale:1});
    return `${simpleCards([['Netimport',kwh(months.reduce((a,m)=>a+m.imp,0))],['Netexport',kwh(months.reduce((a,m)=>a+m.exp,0))],['Boiler',kwh(months.reduce((a,m)=>a+m.bo,0))],['Tesla',kwh(months.reduce((a,m)=>a+m.tes,0))]])}<div class="eh-panel"><div class="eh-panel-title"><h3>Energie-overzicht · jaar ${year}</h3></div><div class="eh-chart-wrap">${ch}</div>${legend([['imp','Netimport'],['exp','Netexport'],['home','Boiler'],['pv','Tesla']])}</div>`;
  }
  async function render(){
    const root=$('#energy-history-dashboard');if(!root)return;root.innerHTML='<div class="eh-shell"><div class="eh-empty">Data laden…</div></div>';
    try{
      const [day,hist]=await Promise.all([get('energy-day-v2.json'),get('energy-daily-history.json')]);let mode='day';
      const shell=document.createElement('div');shell.className='eh-shell';shell.innerHTML=`<div class="eh-toolbar"><div class="eh-tabs"><button class="eh-tab is-active" data-mode="day">Dag</button><button class="eh-tab" data-mode="week">Week</button><button class="eh-tab" data-mode="month">Maand</button><button class="eh-tab" data-mode="year">Jaar</button></div><div class="eh-period">v2 dagdata: ${day.generated_at?new Date(day.generated_at).toLocaleString('nl-NL'):'nog niet'}</div></div><div id="eh-content"></div>`;root.replaceChildren(shell);
      const draw=()=>{$('#eh-content').innerHTML=mode==='day'?dayView(day):mode==='year'?yearView(hist):aggView(hist,mode);shell.querySelectorAll('.eh-tab').forEach(b=>b.classList.toggle('is-active',b.dataset.mode===mode));bindChartInteractions(shell);};
      shell.addEventListener('click',e=>{const b=e.target.closest('.eh-tab');if(b){mode=b.dataset.mode;draw();}});draw();
    }catch(e){root.innerHTML=`<div class="eh-shell"><div class="eh-empty">Energiehistorie kon niet worden geladen: ${e.message}</div></div>`;}
  }
  document.addEventListener('DOMContentLoaded',render);document.addEventListener('DOMContentSwitch',render);
})();
