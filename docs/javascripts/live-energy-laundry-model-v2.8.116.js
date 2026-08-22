(function(){
  'use strict';

  const MAX_AGE_MS=15*60*1000;
  const MIN_SEQUENCE_CONFIDENCE=0.68;
  const scriptSrc=document.currentScript?.src || '';
  const dataUrl=scriptSrc ? new URL('../data/laundry-analysis.json',scriptSrc).href : '/homey-energy-manual/data/laundry-analysis.json';
  let busy=false;
  let lastKey='';
  let lastFingerprintRevision='';

  const finite=v=>Number.isFinite(Number(v));

  function fresh(data){
    const t=Date.parse(data?.meta?.generated_at||'');
    return Number.isFinite(t) && Date.now()-t>=0 && Date.now()-t<=MAX_AGE_MS;
  }

  function mergeOne(rawLoad,modelLoad){
    if(!rawLoad || !modelLoad) return false;
    const sameActive=rawLoad.active===true && modelLoad.active===true;
    const usable=sameActive && modelLoad.estimated===true && finite(modelLoad.power_w) && Number(modelLoad.power_w)>20;
    const had=rawLoad.power_w;
    if(usable){
      rawLoad.power_w=Math.round(Number(modelLoad.power_w));
      rawLoad.power_source='P1_TRANSITION_MODEL';
      rawLoad.power_estimated=true;
      rawLoad.power_confidence=String(modelLoad.confidence||'NONE');
      rawLoad.phase=modelLoad.phase??null;
      rawLoad.evidence_count=Number(modelLoad.evidence_count)||0;
      rawLoad.phase_consistency=Number(modelLoad.phase_consistency)||0;
      return had!==rawLoad.power_w;
    }
    if(rawLoad.active===true && rawLoad.power_source==='P1_TRANSITION_MODEL'){
      rawLoad.power_w=null;
      rawLoad.power_source=null;
      rawLoad.power_estimated=false;
      return true;
    }
    return false;
  }

  function markConflictOnly(washer,candidate,raw,result){
    washer.state={
      ...(washer.state||{}),
      fingerprintConflict:true,
      fingerprintConflictType:'SOURCE_CONFLICT',
      fingerprintConfidence:Number(candidate.confidence),
      fingerprintMethod:candidate.method,
      fingerprintEvidenceOnly:true
    };
    raw.meta.laundry_fingerprint_fallback={
      applied:false,
      conflict:true,
      source_revision:result?.source_revision??null,
      confidence:Number(candidate.confidence),
      method:candidate.method,
      reason:'AEG_HEALTHY_IDLE_P1_SEQUENCE_CONFLICT'
    };
  }

  function applyFingerprintFallback(result){
    const state=window.EnergyCoreV2?.state;
    const raw=state?.raw;
    const washer=raw?.loads?.washer;
    if(!washer) return;
    const candidate=(result?.detections||[]).find(x=>x?.id==='WASMACHINE_CANDIDATE');
    if(!candidate || candidate.method!=='SEQUENTIAL_L2_FINGERPRINT' || candidate.active!==true || Number(candidate.confidence)<MIN_SEQUENCE_CONFIDENCE) return;

    const revision=String(result?.source_revision??raw?.meta?.state_revision??'');
    const key=`${revision}|${candidate.confidence}|${candidate.anchor_mode}|${candidate.direct_source_quality?.status||''}`;
    if(key===lastFingerprintRevision) return;
    lastFingerprintRevision=key;

    // Rule 1: a direct active AEG/Homey state is always authoritative.
    if(candidate.direct_source_quality?.direct_active===true || (washer.active===true && washer.state?.inferred!==true)) return;

    // Rule 2: a usable direct Idle state is not overruled. Fingerprint is diagnostic evidence only.
    if(candidate.status_conflict===true && candidate.direct_source_quality?.status==='HEALTHY_IDLE'){
      markConflictOnly(washer,candidate,raw,result);
      document.dispatchEvent(new CustomEvent('energycorev2state',{detail:state}));
      return;
    }

    // Rule 3: fallback may activate only when the direct source is unavailable, stale or inconsistent.
    if(candidate.fallback_allowed!==true) return;
    washer.active=true;
    washer.power_w=null;
    washer.power_source='P1_SEQUENCE_FINGERPRINT';
    washer.power_estimated=false;
    washer.phase=candidate.phase||'L2';
    washer.state={
      ...(washer.state||{}),
      active:true,
      source:'P1_SEQUENCE_FALLBACK',
      inferred:true,
      conflict:false,
      directSourceQuality:candidate.direct_source_quality?.status||'UNAVAILABLE',
      directReportedState:washer.state?.applianceState||null,
      fingerprintConfidence:Number(candidate.confidence),
      fingerprintMethod:candidate.method
    };
    raw.meta.laundry_fingerprint_fallback={
      applied:true,
      conflict:false,
      source_revision:result?.source_revision??null,
      confidence:Number(candidate.confidence),
      method:candidate.method,
      reason:`AEG_${candidate.direct_source_quality?.status||'UNAVAILABLE'}_P1_SEQUENCE_FALLBACK`
    };
    document.dispatchEvent(new CustomEvent('energycorev2state',{detail:state}));
  }

  async function apply(){
    if(busy) return;
    const state=window.EnergyCoreV2?.state;
    const raw=state?.raw;
    if(!raw?.loads) return;
    busy=true;
    try{
      const r=await fetch(`${dataUrl}?t=${Date.now()}`,{cache:'no-store'});
      if(!r.ok) return;
      const data=await r.json();
      if(!fresh(data)) return;
      const sourceSample=String(raw?.meta?.source_sample_at||raw?.meta?.generated_at||'');
      const key=`${data.meta.generated_at}|${sourceSample}|${raw.loads.washer?.active}|${raw.loads.dryer?.active}`;
      if(key===lastKey) return;
      mergeOne(raw.loads.washer,data.washer);
      mergeOne(raw.loads.dryer,data.dryer);
      raw.meta.laundry_model={generated_at:data.meta.generated_at,model_updated_at:data.meta.model_updated_at||null,threshold_w:data.meta.threshold_w??20,method:data.meta.method||null};
      lastKey=key;
      document.dispatchEvent(new CustomEvent('energycorev2state',{detail:state}));
    }catch(_){
      // Fail safe: no model data is better than a stale estimate.
    }finally{busy=false;}
  }

  document.addEventListener('loadfingerprintstate',e=>setTimeout(()=>applyFingerprintFallback(e.detail),20));
  document.addEventListener('DOMContentLoaded',()=>setTimeout(apply,350));
  document.addEventListener('DOMContentSwitch',()=>setTimeout(apply,200));
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)setTimeout(apply,100);});
  setInterval(apply,5000);
})();