(function(){
  'use strict';
  const BASE='https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-state-v2.json';
  const REFRESH_MS=5*60*1000;
  const MAX_STATE_AGE_MS=15*60*1000;
  const MAX_HEARTBEAT_AGE_MS=45*60*1000;
  let timer=null,current=null;
  const ms=v=>{const t=Date.parse(v||'');return Number.isFinite(t)?t:null;};
  const age=v=>{const t=ms(v);return t===null?null:Date.now()-t;};
  function normalize(raw){
    const schema=String(raw?.meta?.schema_version||'');
    if(!/^2(?:\.|$)/.test(schema)) return null;
    const stateAge=age(raw.meta.generated_at),heartbeatAge=age(raw.meta.heartbeat_at);
    return {raw,stateAgeMs:stateAge,heartbeatAgeMs:heartbeatAge,stateFresh:stateAge!==null&&stateAge<=MAX_STATE_AGE_MS,heartbeatFresh:heartbeatAge!==null&&heartbeatAge<=MAX_HEARTBEAT_AGE_MS,healthy:heartbeatAge!==null&&heartbeatAge<=MAX_HEARTBEAT_AGE_MS,controlMode:String(raw.meta.control_mode||'UNKNOWN'),managerState:String(raw.manager?.state||'UNKNOWN'),decision:String(raw.manager?.decision||'UNKNOWN')};
  }
  async function load(){
    try{
      const sep=BASE.includes('?')?'&':'?';
      const r=await fetch(`${BASE}${sep}ts=${Date.now()}`,{cache:'no-store',mode:'cors'});
      if(!r.ok)throw new Error(`energy-state-v2.json: HTTP ${r.status}`);
      const parsed=normalize(await r.json()); if(!parsed)throw new Error('ongeldig Energy State v2-contract');
      current=parsed;
      window.EnergyCoreV2={available:true,state:current,refresh:load,source:'github-main'};
      document.dispatchEvent(new CustomEvent('energycorev2state',{detail:current}));
      return current;
    }catch(e){
      window.EnergyCoreV2={available:false,state:current,error:String(e?.message||e),refresh:load,source:'github-main'};
      return null;
    }
  }
  function start(){load(); if(timer)clearInterval(timer); timer=setInterval(()=>{if(!document.hidden)load();},REFRESH_MS);}
  window.EnergyCoreV2={available:false,state:null,refresh:load,source:'github-main'};
  document.addEventListener('DOMContentLoaded',start);
  document.addEventListener('DOMContentSwitch',load);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)load();});
})();