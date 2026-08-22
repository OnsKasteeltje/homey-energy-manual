(function(){
  'use strict';

  // Read-only P1 dishwasher fingerprint fallback.
  // Phase map validated for this installation: SolarEdge on L1, GoodWe 4200 on L2,
  // GoodWe 2000 on L3. The dishwasher fingerprint therefore reconstructs gross L1
  // as P1_L1 + SolarEdge AC power. It never writes to Homey and is presentation-only.
  const VERSION='1.0.0';
  const HISTORY_KEY='em2-dishwasher-fingerprint-v1';
  const MAX_HISTORY_MS=3*60*60*1000;
  const ACTIVE_THRESHOLD_W=20;
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
    const gross=Math.max(0,p1L1+pvL1);
    return {signal_w:gross,p1_l1_w:p1L1,pv_l1_w:pvL1};
  }

  function blockers(raw){
    const loads=raw?.loads||{};
    return {
      tesla:raw?.tesla?.charging===true||pwr(raw?.tesla)>ACTIVE_THRESHOLD_W,
      boiler:raw?.hot_water?.boiler_on===true&&pwr({power_w:raw?.hot_water?.boiler_power_w})>ACTIVE_THRESHOLD_W,
      quooker:active(loads.quooker),
      washer:active(loads.washer),
      dryer:active(loads.dryer)
    };
  }

  function readHistory(){try{const x=JSON.parse(localStorage.getItem(HISTORY_KEY)||'[]');return Array.isArray(x)?x:[];}catch(_){return [];}}
  function writeHistory(rows){try{localStorage.setItem(HISTORY_KEY,JSON.stringify(rows));}catch(_){}}
  function addHistory(raw){
    const ts=tsOf(raw),sig=l1Signal(raw),b=blockers(raw);
    if(!sig)return readHistory();
    let rows=readHistory().filter(x=>finite(x?.ts)&&ts-Number(x.ts)<=MAX_HISTORY_MS);
    if(!rows.length||Math.abs(Number(rows.at(-1).ts)-ts)>1000)rows.push({ts,l1_w:sig.signal_w,blocked:Object.values(b).some(Boolean)});
    rows=rows.slice(-80);writeHistory(rows);return rows;
  }

  const band=w=>w>=1750&&w<=2600?'HEAT':(w>=120&&w<=900?'PUMP':(w>=0&&w<=180?'REST':null));

  function classify(raw){
    if(!raw)return {version:VERSION,active:false,confidence:0,power_w:null,reason:'NO_STATE'};
    const sig=l1Signal(raw);if(!sig)return {version:VERSION,active:false,confidence:0,power_w:null,reason:'NO_L1'};
    const b=blockers(raw),blocked=Object.values(b).some(Boolean),history=addHistory(raw),now=tsOf(raw);
    const recent=history.filter(x=>!x.blocked&&now-Number(x.ts)<=120*60*1000&&finite(x.l1_w));
    const currentBand=band(sig.signal_w);
    const heat=recent.filter(x=>band(Number(x.l1_w))==='HEAT').length;
    const pump=recent.filter(x=>band(Number(x.l1_w))==='PUMP').length;
    const rest=recent.filter(x=>band(Number(x.l1_w))==='REST').length;
    let transitions=0,last=null;
    for(const row of recent){const q=band(Number(row.l1_w));if(q&&last&&q!==last)transitions++;if(q)last=q;}

    if(blocked)return {version:VERSION,active:false,confidence:0,power_w:null,reason:'KNOWN_LOAD_CONFLICT',signal:sig,blockers:b};

    let confidence=0;
    const evidence=[];
    if(currentBand==='HEAT'){
      confidence=0.72;
      evidence.push(`L1 verwarmingsband ${Math.round(sig.signal_w)} W`);
      evidence.push('geen bekende grote conflicterende belasting actief');
      if(heat>=2){confidence+=0.05;evidence.push(`${heat} verwarmingssamples`);}
      if(pump>=1){confidence+=0.08;evidence.push(`${pump} pomp/werk-sample(s)`);}
      if(rest>=1){confidence+=0.04;evidence.push(`${rest} rustsample(s)`);}
      if(transitions>=2){confidence+=0.06;evidence.push(`${transitions} fase-overgang(en)`);}
    }else if(currentBand==='PUMP'&&heat>=1&&transitions>=1){
      confidence=0.70+Math.min(0.12,transitions*0.03);
      evidence.push('pomp/werkfase na eerdere L1-verwarmingspuls');
      evidence.push(`${transitions} fase-overgang(en)`);
    }else{
      return {version:VERSION,active:false,confidence:0,power_w:null,reason:'NO_MATCH',signal:sig,sequence:{heat,pump,rest,transitions}};
    }

    confidence=clamp(confidence,0,0.92);
    if(confidence<0.68)return {version:VERSION,active:false,confidence,power_w:null,reason:'LOW_CONFIDENCE',signal:sig,evidence};

    // Presentation estimate only. In HEAT, almost the full reconstructed L1 signal
    // belongs to the dishwasher; preserve a small 100 W household baseline.
    const estimate=currentBand==='HEAT'?clamp(sig.signal_w-100,1700,2400):clamp(sig.signal_w-80,80,850);
    return {
      version:VERSION,active:true,confidence:Number(confidence.toFixed(2)),confidence_level:confidence>=0.80?'HIGH':'MEDIUM',
      power_w:Math.round(estimate),power_estimated:true,power_source:'P1_FINGERPRINT',phase:'L1',method:'SEQUENTIAL_L1_DISHWASHER_FINGERPRINT',
      signal:sig,sequence:{heat,pump,rest,transitions},evidence
    };
  }

  function publish(raw){
    lastRaw=raw||lastRaw||window.EnergyCoreV2?.state?.raw;
    if(!lastRaw)return;
    const state=classify(lastRaw);
    window.DishwasherFingerprint.state=state;
    document.dispatchEvent(new CustomEvent('dishwasherfingerprintstate',{detail:state}));
  }

  window.DishwasherFingerprint={version:VERSION,state:null,classify,refresh:()=>publish()};
  document.addEventListener('energycorev2state',e=>setTimeout(()=>publish(e.detail?.raw),90));
  document.addEventListener('DOMContentLoaded',()=>{setTimeout(()=>publish(),650);setTimeout(()=>publish(),1400);});
  document.addEventListener('DOMContentSwitch',()=>setTimeout(()=>publish(),300));
})();
