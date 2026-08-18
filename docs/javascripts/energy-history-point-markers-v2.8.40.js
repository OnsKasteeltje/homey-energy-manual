(function(){
'use strict';
function drawMarkers(root=document){
  root.querySelectorAll('.eh-chart-interactive').forEach(box=>{
    const svg=box.querySelector('svg');
    if(!svg||box.dataset.pointsV2840==='1')return;
    let labels,series;
    try{labels=JSON.parse(decodeURIComponent(box.dataset.labels||''));series=JSON.parse(decodeURIComponent(box.dataset.series||''));}catch(e){return;}
    if(!Array.isArray(labels)||!labels.length||!Array.isArray(series))return;
    const W=Number(box.dataset.w)||1100,p=Number(box.dataset.pad)||48,H=330;
    const nums=series.flatMap(s=>(s.values||[]).filter(v=>v!==null&&v!==undefined&&Number.isFinite(Number(v))).map(Number));
    if(!nums.length)return;
    const signed=nums.some(v=>v<0),max=Math.max(1,...nums.map(v=>Math.abs(Number(v)))),ymin=signed?-max:0,ymax=max;
    svg.querySelectorAll('.eh-data-point-v2840').forEach(n=>n.remove());
    series.forEach(s=>{
      (s.values||[]).forEach((raw,i)=>{
        if(raw===null||raw===undefined||!Number.isFinite(Number(raw)))return;
        const v=Number(raw),x=p+(W-2*p)*i/Math.max(1,labels.length-1),y=p+(H-2*p)*(1-(v-ymin)/(ymax-ymin||1));
        const c=document.createElementNS('http://www.w3.org/2000/svg','circle');
        c.setAttribute('cx',x.toFixed(1));c.setAttribute('cy',y.toFixed(1));c.setAttribute('r','4.5');
        c.setAttribute('class',`eh-data-point-v2840 eh-line ${s.cls||''}`);
        c.setAttribute('fill','currentColor');c.setAttribute('stroke','currentColor');c.setAttribute('stroke-width','1');
        svg.appendChild(c);
      });
    });
    box.dataset.pointsV2840='1';
  });
}
function schedule(){setTimeout(()=>drawMarkers(document),0);setTimeout(()=>drawMarkers(document),100);}
document.addEventListener('DOMContentLoaded',schedule);
document.addEventListener('DOMContentSwitch',schedule);
document.addEventListener('click',e=>{if(e.target.closest('.eh-tab'))setTimeout(()=>{document.querySelectorAll('.eh-chart-interactive').forEach(b=>delete b.dataset.pointsV2840);drawMarkers(document);},20);});
const obs=new MutationObserver(()=>{document.querySelectorAll('.eh-chart-interactive').forEach(b=>{if(!b.querySelector('.eh-data-point-v2840'))delete b.dataset.pointsV2840;});drawMarkers(document);});
const start=()=>{const r=document.getElementById('energy-history-dashboard');if(r)obs.observe(r,{childList:true,subtree:true});};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
