(function(){
  'use strict';

  // Read-only appliance fingerprint classifier.
  // Consumes already-published Energy Core v2 state only; never calls Homey.
  // v1.1.0 adds a conservative sequential washing-machine fingerprint based on
  // the validated 2026-08-22 L2 reference run. It performs recognition only;
  // no washer wattage is attributed until an independent second clean run validates it.
  const VERSION='1.1.0';
  const HISTORY_KEY='em2-load-fingerprint-history-v2';
  const MAX_HISTORY_MS=3*60*60*1000;
  const ACTIVE_THRESHOLD_W=20;
  let lastRaw=null;

  const finite=v=>Number.isFinite(Number(v));
  const clamp01=v=>Math.max(0,Math.min(1,v));
  const nowFromRaw=raw=>{
    const t=Date.parse(raw?.meta?.generated_at||'');
    return Number.isFinite(t)?t:Date.now();
  };
  const loadPower=o=>o&&finite(o.power_w)?Math.max(0,Number(o.power_w)):null;
  const isActive=o=>o?.active===true || o?.state?.active===true || (loadPower(o)!==null && loadPower(o)>ACTIVE_THRESHOLD_W);
  const residualPower=raw=>{
    const candidates=[raw?.energy_budget?.other_house_load_w,raw?.balance?.residual_w];
    for(const v of candidates){if(finite(v))return Math.max(0,Number(v));}
    return null;
  };
  const phaseImport=(raw,key)=>finite(raw?.grid?.[key])?Math.max(0,Number(raw.grid[key])):null;

  function readHistory(){
    try{const v=JSON.parse(localStorage.getItem(HISTORY_KEY)||'[]');return Array.isArray(v)?v:[];}catch(_){return [];}
  }
  function writeHistory(rows){
    try{localStorage.setItem(HISTORY_KEY,JSON.stringify(rows));}catch(_){}
  }
  function addHistory(raw){
    const ts=nowFromRaw(raw);
    const row={
      ts,
      residual_w:residualPower(raw),
      l2_w:phaseImport(raw,'l2_w'),
      washer_active:isActive(raw?.loads?.washer),
      dryer_active:isActive(raw?.loads?.dryer),
      quooker_active:isActive(raw?.loads?.quooker),
      tesla_active:raw?.tesla?.charging===true || (finite(raw?.tesla?.power_w)&&Number(raw.tesla.power_w)>ACTIVE_THRESHOLD_W),
      boiler_active:raw?.hot_water?.boiler_on===true && finite(raw?.hot_water?.boiler_power_w) && Number(raw.hot_water.boiler_power_w)>ACTIVE_THRESHOLD_W
    };
    let rows=readHistory().filter(x=>finite(x?.ts)&&ts-Number(x.ts)<=MAX_HISTORY_MS);
    if(!rows.length || Math.abs(Number(rows[rows.length-1].ts)-ts)>1000)rows.push(row);
    rows=rows.slice(-50);writeHistory(rows);return rows;
  }

  function quookerCandidate(raw){
    const q=raw?.loads?.quooker||null;
    if(!q)return null;
    const power=loadPower(q),active=isActive(q);
    if(!active)return null;
    const direct=q.measurement==='DIRECT' && power!==null;
    return {
      id:'QUOOKER',label:'Quooker',active:true,
      confidence:direct?1:0.98,confidence_level:'HIGH',
      power_w:power,attribution_w:power,
      method:direct?'DIRECT_PLUS_STATUS':'AUTHORITATIVE_STATUS_PLUS_CONTEXT',
      evidence:[direct?'direct power':'Cooker/Quooker active status','published Energy Core context'],
      inferred:!direct
    };
  }

  function washerSequenceCandidate(raw,history){
    const ts=nowFromRaw(raw);
    const recent=history.filter(x=>finite(x?.ts)&&ts-Number(x.ts)<=160*60*1000);
    if(recent.length<6)return null;

    // Direct AEG status is status ground truth, not a power meter. Find the current/recent
    // cycle anchor from that status, but derive electrical phases only from published P1 L2.
    let anchor=-1;
    for(let i=0;i<recent.length;i++)if(recent[i].washer_active){anchor=i;break;}
    if(anchor<0)return null;
    const cycle=recent.slice(anchor);
    if(cycle.length<4)return null;

    // Exclude samples polluted by other known large/flexible loads. Quooker is especially
    // important because a single resistance pulse must never be enough for washer recognition.
    const clean=cycle.filter(x=>!x.dryer_active&&!x.quooker_active&&!x.tesla_active&&!x.boiler_active&&finite(x.l2_w));
    if(clean.length<4)return null;

    const startTs=Number(cycle[0].ts),elapsedMin=(ts-startTs)/60000;
    const early=clean.filter(x=>(Number(x.ts)-startTs)<=35*60*1000);
    const heating=early.filter(x=>Number(x.l2_w)>=1800&&Number(x.l2_w)<=2600);
    const afterHeatStart=heating.length?Number(heating[0].ts):startTs;
    const after=clean.filter(x=>Number(x.ts)>=afterHeatStart);
    const work=after.filter(x=>Number(x.l2_w)>=250&&Number(x.l2_w)<=700);
    const rest=after.filter(x=>Number(x.l2_w)>=40&&Number(x.l2_w)<=240);
    const tail=after.filter(x=>(Number(x.ts)-startTs)>=70*60*1000&&Number(x.l2_w)>=100&&Number(x.l2_w)<=260);

    let alternations=0,lastBand=null;
    for(const x of after){
      const w=Number(x.l2_w);
      const band=w>=250&&w<=700?'WORK':(w>=40&&w<=240?'REST':null);
      if(band&&lastBand&&band!==lastBand)alternations++;
      if(band)lastBand=band;
    }

    const hasHeating=heating.length>=1;
    const hasWork=work.length>=2;
    const hasRest=rest.length>=1;
    const hasAlternation=alternations>=2;
    const durationEvidence=elapsedMin>=45;
    const tailEvidence=tail.length>=1;
    const directNow=isActive(raw?.loads?.washer);
    const sequenceEvidence=[hasHeating,hasWork,hasRest,hasAlternation,durationEvidence].filter(Boolean).length;

    // Require a multi-stage sequence. One 2 kW pulse can be Quooker/kettle/oven and is rejected.
    if(sequenceEvidence<4 || !hasWork || !hasRest)return null;

    let confidence=0.42;
    if(hasHeating)confidence+=0.12;
    if(hasWork)confidence+=Math.min(0.10,work.length*0.025);
    if(hasRest)confidence+=0.05;
    if(hasAlternation)confidence+=Math.min(0.10,alternations*0.025);
    if(durationEvidence)confidence+=0.07;
    if(tailEvidence)confidence+=0.05;
    if(directNow)confidence+=0.08;
    // Reference-only guard: one clean reference run is not enough for HIGH production attribution.
    confidence=Math.min(0.84,clamp01(confidence));

    const cycleLooksComplete=!directNow && cycle.some(x=>x.washer_active) && elapsedMin>=70;
    return {
      id:'WASMACHINE_CANDIDATE',label:'Wasmachine',active:directNow||!cycleLooksComplete,
      confidence:Number(confidence.toFixed(2)),
      confidence_level:confidence>=0.60?'MEDIUM':'LOW',
      power_w:null,attribution_w:null,
      method:'SEQUENTIAL_L2_FINGERPRINT',
      validation_status:'REFERENCE_ONLY',
      phase:'L2',
      sequence:{
        elapsed_min:Number(elapsedMin.toFixed(1)),
        heating_samples:heating.length,
        work_samples:work.length,
        rest_samples:rest.length,
        work_rest_alternations:alternations,
        tail_samples:tail.length,
        direct_aeg_active:directNow,
        cycle_complete_candidate:cycleLooksComplete
      },
      evidence:[
        hasHeating?`${heating.length} L2 verwarmingspuls(en) 1,8–2,6 kW`:'geen vroege verwarmingspuls gezien',
        `${work.length} L2 werkblok(ken) 0,25–0,70 kW`,
        `${rest.length} lage/rustsample(s)`,
        `${alternations} werk/rust-overgang(en)`,
        `${Math.round(elapsedMin)} min sinds AEG-startanker`,
        tailEvidence?'L2 staartfase 0,10–0,26 kW gezien':'staartfase nog niet gezien',
        'geen vermogensattributie tot tweede onafhankelijke schone run'
      ],
      inferred:true
    };
  }

  function ovenCandidate(raw,history){
    if(isActive(raw?.loads?.quooker)||isActive(raw?.loads?.washer))return null;
    const current=residualPower(raw);if(current===null)return null;
    const recent=history.filter(x=>!x.quooker_active&&!x.washer_active&&nowFromRaw(raw)-Number(x.ts)<=45*60*1000&&finite(x.residual_w));
    if(recent.length<4)return null;
    const high=recent.filter(x=>Number(x.residual_w)>=1200),low=recent.filter(x=>Number(x.residual_w)<=700);
    let transitions=0;
    for(let i=1;i<recent.length;i++)if(Math.abs(Number(recent[i-1].residual_w)-Number(recent[i].residual_w))>=900)transitions++;
    const cyclic=high.length>=2&&low.length>=1&&transitions>=2;
    if(!cyclic||current<900)return null;
    const confidence=clamp01(0.58+Math.min(0.18,transitions*0.04)+Math.min(0.12,high.length*0.03));
    return {id:'ATAG_OVEN',label:'ATAG oven',active:true,confidence:Number(confidence.toFixed(2)),confidence_level:confidence>=0.75?'HIGH':'MEDIUM',power_w:null,attribution_w:null,method:'CYCLIC_RESIDUAL_FINGERPRINT',evidence:[`${high.length} hoge residual-samples`,`${low.length} lage residual-samples`,`${transitions} grote overgangen`],inferred:true};
  }

  function kettleCandidate(raw,history){
    if(isActive(raw?.loads?.quooker)||isActive(raw?.loads?.washer))return null;
    const current=residualPower(raw);if(current===null||current<1800)return null;
    const ts=nowFromRaw(raw),recent=history.filter(x=>finite(x.residual_w)&&ts-Number(x.ts)<=15*60*1000);
    if(recent.length<2)return null;
    const previous=recent.slice(0,-1).at(-1);if(!previous||Number(previous.residual_w)>800)return null;
    return {id:'WATERKOKER_CANDIDATE',label:'Waterkoker?',active:true,confidence:0.45,confidence_level:'LOW',power_w:null,attribution_w:null,method:'SHORT_HIGH_LOAD_CANDIDATE',evidence:['korte sterke residual-sprong','nog niet uniek genoeg gevalideerd'],inferred:true};
  }

  function classify(raw){
    if(!raw)return {version:VERSION,generated_at:new Date().toISOString(),detections:[],best:null};
    const history=addHistory(raw),detections=[];
    [quookerCandidate(raw),washerSequenceCandidate(raw,history),ovenCandidate(raw,history),kettleCandidate(raw,history)].filter(Boolean).forEach(x=>detections.push(x));
    detections.sort((a,b)=>b.confidence-a.confidence);
    return {version:VERSION,generated_at:raw?.meta?.generated_at||new Date().toISOString(),source_revision:raw?.meta?.state_revision??raw?.meta?.revision??null,read_only:true,detections,best:detections[0]||null};
  }

  function render(result){
    const root=document.getElementById('live-energy-flow');if(!root)return;
    root.querySelector('.load-fingerprint-status')?.remove();
    const best=result?.best;
    root.dataset.fingerprintVersion=VERSION;root.dataset.fingerprintBest=best?.id||'NONE';root.dataset.fingerprintConfidence=best?String(best.confidence):'0';
    const box=document.createElement('div');box.className='load-fingerprint-status';
    if(!best)box.innerHTML='<strong>Apparaatherkenning:</strong> geen fingerprint met voldoende bewijs.';
    else{const pct=Math.round(best.confidence*100),kind=best.inferred?'inferred':'direct/status';box.innerHTML=`<strong>Apparaatherkenning:</strong> ${best.label} · ${pct}% · ${kind}<br><small>${best.evidence.join(' · ')}</small>`;}
    root.appendChild(box);
  }

  function publish(raw){
    lastRaw=raw||lastRaw||window.EnergyCoreV2?.state?.raw;if(!lastRaw)return;
    const result=classify(lastRaw);window.LoadFingerprintClassifier.state=result;render(result);document.dispatchEvent(new CustomEvent('loadfingerprintstate',{detail:result}));
  }

  window.LoadFingerprintClassifier={version:VERSION,state:null,classify,refresh:()=>publish()};
  document.addEventListener('energycorev2state',e=>setTimeout(()=>publish(e.detail?.raw),70));
  document.addEventListener('DOMContentLoaded',()=>{setTimeout(()=>publish(),500);setTimeout(()=>publish(),1300);});
  document.addEventListener('DOMContentSwitch',()=>setTimeout(()=>publish(),250));
})();
