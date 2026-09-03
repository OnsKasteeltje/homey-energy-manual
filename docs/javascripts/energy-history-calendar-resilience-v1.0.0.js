(function(){
'use strict';
const BASE='/homey-energy-manual/data/';
const iso=d=>{const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),day=String(d.getDate()).padStart(2,'0');return `${y}-${m}-${day}`;};
const fullLabel=date=>new Date(`${date}T12:00:00`).toLocaleDateString('nl-NL',{weekday:'short',day:'numeric',month:'short'}).replace('.','');
const get=async f=>{const r=await fetch(`${BASE}${f}?ts=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`${f}: ${r.status}`);return r.json();};
let busy=false,lastSignature='';
async function repairPicker(){
  if(busy)return;
  const root=document.querySelector('#energy-history-dashboard');
  const select=root?.querySelector('#eh-day-select');
  if(!root||!select)return;
  busy=true;
  try{
    const [day,rolling]=await Promise.all([get('energy-day-v2.json'),get('energy-day-series-7d.json').catch(()=>({days:[]}))]);
    const current=day?.date_local;
    if(!current)return;
    const available=new Set((rolling.days||[]).map(d=>d?.date_local).filter(Boolean));
    available.add(current);
    const currentDate=new Date(`${current}T12:00:00`);
    const dates=[];
    for(let offset=0;offset<7;offset++){
      const d=new Date(currentDate);d.setDate(currentDate.getDate()-offset);dates.push(iso(d));
    }
    const signature=dates.map(d=>`${d}:${available.has(d)?1:0}`).join('|');
    if(signature===lastSignature&&select.options.length===7)return;
    const selected=select.value||current;
    const yesterday=dates[1];
    select.replaceChildren(...dates.map(date=>{
      const option=document.createElement('option');
      option.value=date;
      const base=date===current?'vandaag':date===yesterday?'gisteren':fullLabel(date);
      option.textContent=available.has(date)?base:`${base} · geen dagarchief`;
      return option;
    }));
    select.value=dates.includes(selected)?selected:current;
    lastSignature=signature;
  } finally {busy=false;}
}
document.addEventListener('EnergyHistoryDayChanged',()=>{repairPicker().catch(()=>{});});
document.addEventListener('DOMContentLoaded',()=>{setTimeout(()=>repairPicker().catch(()=>{}),250);});
document.addEventListener('DOMContentSwitch',()=>{setTimeout(()=>repairPicker().catch(()=>{}),250);});
})();
