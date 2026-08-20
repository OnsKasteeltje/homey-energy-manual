(function(){
  'use strict';

  const Store=window.EnergyStore;
  if(!Store){
    console.error('EnergyStore ontbreekt; Energy Core v2 adapter niet gestart.');
    return;
  }

  const BASE='https://raw.githubusercontent.com/OnsKasteeltje/homey-energy-manual/main/docs/data/energy-state-v2.json';
  const REFRESH_MS=5*60*1000;
  const MAX_STATE_AGE_MS=15*60*1000;
  const MAX_HEARTBEAT_AGE_MS=45*60*1000;
  const SUPPORTED_SCHEMAS=new Set(['2.10']);
  let timer=null;

  const ms=v=>{const t=Date.parse(v||'');return Number.isFinite(t)?t:null;};
  const age=v=>{const t=ms(v);return t===null?null:Date.now()-t;};
  const finite=v=>Number.isFinite(Number(v));

  function contractError(raw){
    const schema=String(raw?.meta?.schema_version||'');
    if(!SUPPORTED_SCHEMAS.has(schema)) return `niet-ondersteund schema ${schema||'(ontbreekt)'}`;
    if(!raw?.meta||!raw?.grid||!raw?.pv||!raw?.battery) return 'verplichte Energy State-secties ontbreken';
    if(!finite(raw?.grid?.power_w)) return 'grid.power_w ontbreekt of is ongeldig';
    if(!finite(raw?.meta?.state_revision)||!finite(raw?.meta?.decision_revision)||!finite(raw?.meta?.shadow_revision)) return 'revisionvelden ontbreken of zijn ongeldig';
    const revisions=[Number(raw.meta.state_revision),Number(raw.meta.decision_revision),Number(raw.meta.shadow_revision)];
    if(new Set(revisions).size!==1) return `revision mismatch ${revisions.join('/')}`;
    return null;
  }

  function normalize(raw){
    const contractIssue=contractError(raw);
    if(contractIssue) throw new Error(`ongeldig Energy State v2-contract: ${contractIssue}`);
    const stateAge=age(raw.meta.generated_at);
    const heartbeatAge=age(raw.meta.heartbeat_at);
    return {
      raw,
      stateAgeMs:stateAge,
      heartbeatAgeMs:heartbeatAge,
      stateFresh:stateAge!==null&&stateAge>=0&&stateAge<=MAX_STATE_AGE_MS,
      heartbeatFresh:heartbeatAge!==null&&heartbeatAge>=0&&heartbeatAge<=MAX_HEARTBEAT_AGE_MS,
      healthy:heartbeatAge!==null&&heartbeatAge>=0&&heartbeatAge<=MAX_HEARTBEAT_AGE_MS,
      controlMode:String(raw.meta.control_mode||'UNKNOWN'),
      managerState:String(raw.manager?.state||'UNKNOWN'),
      decision:String(raw.manager?.decision||'UNKNOWN')
    };
  }

  function legacyFacade(){
    return {
      get available(){return !!Store.getState()&&!Store.getError();},
      get state(){return Store.getState();},
      get error(){return Store.getError();},
      refresh:()=>Store.refresh(),
      source:'github-main',
      supportedSchemas:[...SUPPORTED_SCHEMAS]
    };
  }

  function publishState(parsed){
    Store.setSnapshot(parsed);
    document.dispatchEvent(new CustomEvent('energycorev2state',{detail:parsed}));
    if(!parsed.stateFresh||!parsed.heartbeatFresh){
      document.dispatchEvent(new CustomEvent('energycorev2stale',{detail:{state:parsed,stateFresh:parsed.stateFresh,heartbeatFresh:parsed.heartbeatFresh}}));
    }
  }

  function publishError(error){
    const message=String(error?.message||error);
    Store.setError(message);
    document.dispatchEvent(new CustomEvent('energycorev2error',{detail:{message,error,state:Store.getState()}}));
  }

  async function load(){
    try{
      const sep=BASE.includes('?')?'&':'?';
      const response=await fetch(`${BASE}${sep}ts=${Date.now()}`,{cache:'no-store',mode:'cors'});
      if(!response.ok) throw new Error(`energy-state-v2.json: HTTP ${response.status}`);
      const parsed=normalize(await response.json());
      publishState(parsed);
      return parsed;
    }catch(error){
      publishError(error);
      return null;
    }
  }

  function start(){
    load();
    if(timer) clearInterval(timer);
    timer=setInterval(()=>{if(!document.hidden)load();},REFRESH_MS);
  }

  Store.setRefresh(load);
  Object.defineProperty(window,'EnergyCoreV2',{configurable:true,enumerable:true,get:legacyFacade});
  document.addEventListener('DOMContentLoaded',start);
  document.addEventListener('DOMContentSwitch',load);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)load();});
})();
