(function(){
'use strict';
const VERSION='1.0.0',THRESHOLD=20;let lastRaw=null,lastHighAt=0;
const finite=v=>v!==null&&v!==undefined&&Number.isFinite(Number(v));
const pwr=o=>o&&finite(o.power_w)?Math.max(0,Number(o.power_w)):0;
const active=o=>o?.active===true||o?.state?.active===true||pwr(o)>THRESHOLD;
function blockers(r){const l=r?.loads||{};return {tesla:r?.tesla?.charging===true||pwr(r?.tesla)>THRESHOLD,boiler:r?.hot_water?.boiler_on===true&&Number(r?.hot_water?.boiler_power_w)>THRESHOLD,quooker:active(l.quooker),washer:active(l.washer),dryer:active(l.dryer),dishwasher:window.DishwasherFingerprint?.state?.active===true};}
function signal(r){if(!finite(r?.grid?.l2_w))return null;const p1=Number(r.grid.l2_w),pv=finite(r?.pv?.goodwe_4200_w)?Math.max(0,Number(r.pv.goodwe_4200_w)):0;return {gross_l2_w:Math.max(0,p1+pv),p1_l2_w:p1,pv_l2_w:pv};}
function classify(r){if(!r)return {version:VERSION,active:false,confidence:0,reason:'NO_STATE'};const s=signal(r);if(!s)return {version:VERSION,active:false,confidence:0,reason:'NO_L2'};const b=blockers(r);if(Object.values(b).some(Boolean))return {version:VERSION,active:false,confidence:0,reason:'KNOWN_LOAD_CONFLICT',signal:s,blockers:b};
const w=s.gross_l2_w,now=Date.now();if(w>=2100&&w<=2900){lastHighAt=now;const est=Math.max(1900,Math.min(2500,w-320));return {version:VERSION,active:true,confidence:0.94,confidence_level:'HIGH',power_w:Math.round(est),power_estimated:true,power_source:'P1_FINGERPRINT',phase:'L2',method:'SHORT_RESISTIVE_L2_STEP',signal:s,evidence:['gevalideerde waterkokerband 2,1–2,9 kW bruto L2','geen bekende conflicterende belasting actief','ground-truth 2026-08-22: +2,216 kW L2']};}
if(lastHighAt&&now-lastHighAt<180000&&w<900)return {version:VERSION,active:false,confidence:0.98,reason:'OFF_TRANSITION_CONFIRMED',signal:s,evidence:['L2 teruggevallen na waterkokerpuls']};return {version:VERSION,active:false,confidence:0,reason:'NO_MATCH',signal:s};}
function publish(r){lastRaw=r||lastRaw||window.EnergyCoreV2?.state?.raw;if(!lastRaw)return;const state=classify(lastRaw);window.KettleFingerprint.state=state;document.dispatchEvent(new CustomEvent('kettlefingerprintstate',{detail:state}));}
window.KettleFingerprint={version:VERSION,state:null,classify,refresh:()=>publish()};document.addEventListener('energycorev2state',e=>setTimeout(()=>publish(e.detail?.raw),100));document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>publish(),800));document.addEventListener('DOMContentSwitch',()=>setTimeout(()=>publish(),350));
})();