(function(){
  'use strict';

  // Read-only P1 dishwasher fingerprint fallback.
  // v1.0.2 hardening after 2026-08-23 ground truth: dishwasher OFF while a short
  // ~2 kW household event (waterkoker just used) produced a false dishwasher HEAT match.
  // An isolated HEAT-band sample is therefore never sufficient anymore.
  const VERSION='1.0.2';
  const HISTORY_KEY='em2-dishwasher-fingerprint-v3';
  const MAX_HISTORY_MS=3*60*60*1000;
  const ACTIVE_THRESHOLD_W=20;
  const TAIL_MAX_AGE_MS=12*60*1000;
  const OFF_CONFIRM_MS=8*60*1000;
  const HEAT_CONFIRM_WINDOW_MS=20*60*1000;
  const PUMP_CONTEXT_MS=45*60*1000;
  let lastRaw=null;

  const finite=v=>v!==null&&v!==undefined&&Number.isFinite(Number(v));
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const tsOf=raw=>{const t=Date.parse(raw?.meta?.generated_at||'');return Number.isFinite(t)?t:Date.now();};
  const pwr=o=>o&&finite(o.power_w)?Math.max(0,Number(o.power_w)):0;
  const active=o=>o?.active===true||o?.state?.active===true||pwr(o)>ACTIVE_THRESHOLD_W;

  function l1Signal(raw){
    if(!finite(raw?.grid?.l1_w))return null;
    const p1L1=Number(raw.grid.l1_w);
    const pvL1=finite(raw?.pv?.solaredge_w)?Math.max(0,Number(raw.pv.solaredge_w)):0;
    return {signal_w:Math.max(0,p1L1+pvL1),p1_l1_w:p1L1,pv_l1_w:pvL1};
  }

  function blockers(raw){
    const loads=raw?.loads||{};
    return {
      tesla:raw?.tesla?.charging===true||pwr(raw?.tesla)>ACTIVE_THRESHOLD_W,
      boiler:raw?.hot_water?.boiler_on===true&&pwr({power_w:raw?.hot_water?.boiler_power_w})>ACTIVE_THRESHOLD_W,
      quooker:active(loads.quooker),washer:active(loads.washer),dryer:active(loads.dryer)
    };
  }

  function readHistory(){try{const x=JSON.parse(localStorage.getItem(HISTORY_KEY)||'[]');return Array.isArray(x)?x:[];}catch(_){return [];}}
  function writeHistory(rows){try{localStorage.setItem(HISTORY_KEY,JSON.stringify(rows));}catch(_){}}
  function addHistory(raw){
    const ts=tsOf(raw),sig=l1Signal(raw),b=blockers(raw);if(!sig)return readHistory();
    let rows=readHistory().filter(x=>finite(x?.ts)&&ts-Number(x.ts)<=MAX_HISTORY_MS);
    if(!rows.length||Math.abs(Number(rows.at(-1).ts)-ts)>1000)rows.push({ts,l1_w:sig.signal_w,blocked:Object.values(b).some(Boolean)});
    rows=rows.slice(-90);writeHistory(rows);return rows;
  }

  const band=w=>w>=1750&&w<=2600?'HEAT':(w>=220&&w<=900?'PUMP':(w>=40&&w<220?'TAIL_LOW':(w>=0&&w<40?'OFF_LOW':null)));

  function classify(raw){
    if(!raw)return {version:VERSION,active:false,confidence:0,power_w:null,reason:'NO_STATE'};
    const sig=l1Signal(raw);if(!sig)return {version:VERSION,active:false,confidence:0,power_w:null,reason:'NO_L1'};
    const b=blockers(raw),blocked=Object.values(b).some(Boolean),history=addHistory(raw),now=tsOf(raw);
    const recent=history.filter(x=>!x.blocked&&now-Number(x.ts)<=120*60*1000&&finite(x.l1_w));
    const currentBand=band(sig.signal_w);
    const heatRows=recent.filter(x=>band(Number(x.l1_w))==='HEAT');
    const pumpRows=recent.filter(x=>band(Number(x.l1_w))==='PUMP');
    const tailRows=recent.filter(x=>band(Number(x.l1_w))==='TAIL_LOW');
    const heat=heatRows.length,pump=pumpRows.length,tail=tailRows.length;
    let transitions=0,last=null;
    for(const row of recent){const q=band(Number(row.l1_w));if(q&&last&&q!==last)transitions++;if(q)last=q;}

    if(blocked)return {version:VERSION,active:false,confidence:0,power_w:null,reason:'KNOWN_LOAD_CONFLICT',signal:sig,blockers:b};

    const recentHeat=heatRows.filter(x=>now-Number(x.ts)<=HEAT_CONFIRM_WINDOW_MS);
    const recentPump=pumpRows.filter(x=>now-Number(x.ts)<=PUMP_CONTEXT_MS);
    const heatSequenceConfirmed=recentHeat.length>=2||recentPump.length>=1;
    const lastStrong=[...heatRows,...pumpRows].sort((a,b)=>Number(a.ts)-Number(b.ts)).at(-1)||null;
    const sinceStrongMs=lastStrong?now-Number(lastStrong.ts):Infinity;
    const lowSinceStrong=lastStrong?recent.filter(x=>Number(x.ts)>Number(lastStrong.ts)&&Number(x.l1_w)<220):[];
    const lowSpanMs=lowSinceStrong.length>=2?Number(lowSinceStrong.at(-1).ts)-Number(lowSinceStrong[0].ts):0;

    let confidence=0;const evidence=[];
    if(currentBand==='HEAT'){
      if(!heatSequenceConfirmed){
        return {version:VERSION,active:false,confidence:0.35,power_w:null,reason:'ISOLATED_HEAT_SPIKE_REJECTED',signal:sig,sequence:{heat,pump,tail,transitions,recent_heat:recentHeat.length,recent_pump:recentPump.length},evidence:['2026-08-23 ground truth: vaatwasser UIT tijdens korte ~2 kW gebeurtenis','één HEAT-band sample is onvoldoende; wacht op tweede HEAT-sample of pompcontext']};
      }
      confidence=recentPump.length?0.84:0.72;
      evidence.push(`L1 verwarmingsband ${Math.round(sig.signal_w)} W`,'HEAT-sequentie bevestigd');
      if(recentHeat.length>=2)evidence.push(`${recentHeat.length} HEAT-samples binnen 20 min`);
      if(recentPump.length>=1)evidence.push(`${recentPump.length} recente pomp/werk-sample(s)`);
      if(transitions>=2){confidence+=0.04;evidence.push(`${transitions} fase-overgang(en)`);}
    }else if(currentBand==='PUMP'&&heat>=1&&sinceStrongMs<=PUMP_CONTEXT_MS){
      confidence=0.74+Math.min(0.12,transitions*0.03);evidence.push('pomp/werkfase na bevestigde verwarmingspuls',`${transitions} fase-overgang(en)`);
    }else if(currentBand==='TAIL_LOW'&&heat>=1&&pump>=1&&sinceStrongMs<=TAIL_MAX_AGE_MS&&lowSpanMs<OFF_CONFIRM_MS){
      confidence=0.70+Math.min(0.08,transitions*0.02);evidence.push('lage staartfase kort na bevestigde werkfase','lage belasting nog niet lang genoeg voor OFF-bevestiging');
    }else if((currentBand==='TAIL_LOW'||currentBand==='OFF_LOW')&&heat>=1&&pump>=1&&(sinceStrongMs>TAIL_MAX_AGE_MS||lowSpanMs>=OFF_CONFIRM_MS)){
      return {version:VERSION,active:false,confidence:0.93,power_w:0,reason:'CYCLE_END_CONFIRMED',signal:sig,sequence:{heat,pump,tail,transitions,since_strong_min:Number((sinceStrongMs/60000).toFixed(1)),low_span_min:Number((lowSpanMs/60000).toFixed(1))},evidence:['aanhoudend lage L1-belasting na eerdere HEAT+PUMP-sequentie']};
    }else{
      return {version:VERSION,active:false,confidence:0,power_w:null,reason:'NO_MATCH',signal:sig,sequence:{heat,pump,tail,transitions}};
    }

    confidence=clamp(confidence,0,0.94);
    if(confidence<0.68)return {version:VERSION,active:false,confidence,power_w:null,reason:'LOW_CONFIDENCE',signal:sig,evidence};
    const estimate=currentBand==='HEAT'?clamp(sig.signal_w-100,1700,2400):(currentBand==='PUMP'?clamp(sig.signal_w-80,140,850):clamp(sig.signal_w-80,40,180));
    return {version:VERSION,active:true,confidence:Number(confidence.toFixed(2)),confidence_level:confidence>=0.80?'HIGH':'MEDIUM',power_w:Math.round(estimate),power_estimated:true,power_source:'P1_FINGERPRINT',phase:'L1',method:'SEQUENTIAL_L1_DISHWASHER_FINGERPRINT',signal:sig,sequence:{heat,pump,tail,transitions,since_strong_min:Number((sinceStrongMs/60000).toFixed(1)),low_span_min:Number((lowSpanMs/60000).toFixed(1))},evidence};
  }

  function publish(raw){lastRaw=raw||lastRaw||window.EnergyCoreV2?.state?.raw;if(!lastRaw)return;const state=classify(lastRaw);window.DishwasherFingerprint.state=state;document.dispatchEvent(new CustomEvent('dishwasherfingerprintstate',{detail:state}));}
  window.DishwasherFingerprint={version:VERSION,state:null,classify,refresh:()=>publish()};
  document.addEventListener('energycorev2state',e=>setTimeout(()=>publish(e.detail?.raw),90));
  document.addEventListener('DOMContentLoaded',()=>{setTimeout(()=>publish(),650);setTimeout(()=>publish(),1400);});
  document.addEventListener('DOMContentSwitch',()=>setTimeout(()=>publish(),300));
})();
