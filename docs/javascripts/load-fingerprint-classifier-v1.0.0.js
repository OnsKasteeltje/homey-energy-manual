(function(){
  'use strict';

  // Read-only appliance fingerprint classifier.
  // It consumes the already published Energy Core v2 state and never calls Homey.
  const VERSION='1.0.0';
  const HISTORY_KEY='em2-load-fingerprint-history-v1';
  const MAX_HISTORY_MS=60*60*1000;
  const ACTIVE_THRESHOLD_W=20;
  let lastRaw=null;

  const finite=v=>Number.isFinite(Number(v));
  const num=v=>finite(v)?Number(v):null;
  const clamp01=v=>Math.max(0,Math.min(1,v));
  const nowFromRaw=raw=>{
    const t=Date.parse(raw?.meta?.generated_at||'');
    return Number.isFinite(t)?t:Date.now();
  };
  const loadPower=o=>o&&finite(o.power_w)?Math.max(0,Number(o.power_w)):null;
  const isActive=o=>o?.active===true || (loadPower(o)!==null && loadPower(o)>ACTIVE_THRESHOLD_W);
  const residualPower=raw=>{
    const candidates=[raw?.energy_budget?.other_house_load_w,raw?.balance?.residual_w];
    for(const v of candidates){if(finite(v))return Math.max(0,Number(v));}
    return null;
  };

  function readHistory(){
    try{const v=JSON.parse(localStorage.getItem(HISTORY_KEY)||'[]');return Array.isArray(v)?v:[];}catch(_){return [];}
  }
  function writeHistory(rows){
    try{localStorage.setItem(HISTORY_KEY,JSON.stringify(rows));}catch(_){}
  }
  function addHistory(raw){
    const ts=nowFromRaw(raw),residual=residualPower(raw),quooker=raw?.loads?.quooker||null;
    const row={ts,residual_w:residual,quooker_active:isActive(quooker)};
    let rows=readHistory().filter(x=>finite(x?.ts)&&ts-Number(x.ts)<=MAX_HISTORY_MS);
    if(!rows.length || Math.abs(Number(rows[rows.length-1].ts)-ts)>1000)rows.push(row);
    rows=rows.slice(-30);writeHistory(rows);return rows;
  }

  function quookerCandidate(raw){
    const q=raw?.loads?.quooker||null;
    if(!q)return null;
    const power=loadPower(q),active=isActive(q);
    if(!active)return null;
    // Cooker/Quooker status is authoritative. A direct watt value, when present,
    // strengthens evidence but is not required for recognition.
    const direct=q.measurement==='DIRECT' && power!==null;
    return {
      id:'QUOOKER',label:'Quooker',active:true,
      confidence:direct?1:0.98,
      confidence_level:'HIGH',
      power_w:power,
      attribution_w:power,
      method:direct?'DIRECT_PLUS_STATUS':'AUTHORITATIVE_STATUS_PLUS_CONTEXT',
      evidence:[direct?'direct power':'Cooker/Quooker active status','published Energy Core context'],
      inferred:!direct
    };
  }

  function ovenCandidate(raw,history){
    if(isActive(raw?.loads?.quooker))return null;
    const current=residualPower(raw);
    if(current===null)return null;
    // ATAG fingerprint is intentionally conservative: the validated fingerprint is cyclic.
    // We therefore require repeated high/low residual changes instead of identifying a
    // single large load spike as the oven. Thresholds are generic candidate gates, not a
    // claimed exact ATAG watt fingerprint.
    const recent=history.filter(x=>!x.quooker_active && nowFromRaw(raw)-Number(x.ts)<=45*60*1000 && finite(x.residual_w));
    if(recent.length<4)return null;
    const high=recent.filter(x=>Number(x.residual_w)>=1200);
    const low=recent.filter(x=>Number(x.residual_w)<=700);
    let transitions=0;
    for(let i=1;i<recent.length;i++){
      const a=Number(recent[i-1].residual_w),b=Number(recent[i].residual_w);
      if(Math.abs(a-b)>=900)transitions++;
    }
    const cyclic=high.length>=2 && low.length>=1 && transitions>=2;
    if(!cyclic || current<900)return null;
    const confidence=clamp01(0.58 + Math.min(0.18,transitions*0.04) + Math.min(0.12,high.length*0.03));
    return {
      id:'ATAG_OVEN',label:'ATAG oven',active:true,
      confidence:Number(confidence.toFixed(2)),
      confidence_level:confidence>=0.75?'HIGH':'MEDIUM',
      power_w:null,
      attribution_w:null,
      method:'CYCLIC_RESIDUAL_FINGERPRINT',
      evidence:[`${high.length} hoge residual-samples`,`${low.length} lage residual-samples`,`${transitions} grote overgangen`],
      inferred:true
    };
  }

  function kettleCandidate(raw,history){
    if(isActive(raw?.loads?.quooker))return null;
    const current=residualPower(raw);if(current===null || current<1800)return null;
    const ts=nowFromRaw(raw),recent=history.filter(x=>finite(x.residual_w)&&ts-Number(x.ts)<=15*60*1000);
    if(recent.length<2)return null;
    const previous=recent.slice(0,-1).at(-1);if(!previous || Number(previous.residual_w)>800)return null;
    return {
      id:'WATERKOKER_CANDIDATE',label:'Waterkoker?',active:true,
      confidence:0.45,confidence_level:'LOW',power_w:null,attribution_w:null,
      method:'SHORT_HIGH_LOAD_CANDIDATE',
      evidence:['korte sterke residual-sprong','nog niet uniek genoeg gevalideerd'],inferred:true
    };
  }

  function classify(raw){
    if(!raw)return {version:VERSION,generated_at:new Date().toISOString(),detections:[],best:null};
    const history=addHistory(raw),detections=[];
    [quookerCandidate(raw),ovenCandidate(raw,history),kettleCandidate(raw,history)].filter(Boolean).forEach(x=>detections.push(x));
    detections.sort((a,b)=>b.confidence-a.confidence);
    return {
      version:VERSION,
      generated_at:raw?.meta?.generated_at||new Date().toISOString(),
      source_revision:raw?.meta?.state_revision??raw?.meta?.revision??null,
      read_only:true,
      detections,
      best:detections[0]||null
    };
  }

  function render(result){
    const root=document.getElementById('live-energy-flow');if(!root)return;
    root.querySelector('.load-fingerprint-status')?.remove();
    const best=result?.best;
    root.dataset.fingerprintVersion=VERSION;
    root.dataset.fingerprintBest=best?.id||'NONE';
    root.dataset.fingerprintConfidence=best?String(best.confidence):'0';
    const box=document.createElement('div');box.className='load-fingerprint-status';
    if(!best){box.innerHTML='<strong>Apparaatherkenning:</strong> geen fingerprint met voldoende bewijs.';}
    else{
      const pct=Math.round(best.confidence*100),kind=best.inferred?'inferred':'direct/status';
      box.innerHTML=`<strong>Apparaatherkenning:</strong> ${best.label} · ${pct}% · ${kind}<br><small>${best.evidence.join(' · ')}</small>`;
    }
    root.appendChild(box);
  }

  function publish(raw){
    lastRaw=raw||lastRaw||window.EnergyCoreV2?.state?.raw;if(!lastRaw)return;
    const result=classify(lastRaw);window.LoadFingerprintClassifier.state=result;render(result);
    document.dispatchEvent(new CustomEvent('loadfingerprintstate',{detail:result}));
  }

  window.LoadFingerprintClassifier={version:VERSION,state:null,classify,refresh:()=>publish()};
  document.addEventListener('energycorev2state',e=>setTimeout(()=>publish(e.detail?.raw),70));
  document.addEventListener('DOMContentLoaded',()=>{setTimeout(()=>publish(),500);setTimeout(()=>publish(),1300);});
  document.addEventListener('DOMContentSwitch',()=>setTimeout(()=>publish(),250));
})();
