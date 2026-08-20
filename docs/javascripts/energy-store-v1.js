(function(){
  'use strict';

  let snapshot=null;
  let error=null;
  let refreshFn=null;
  const listeners=new Set();

  function emit(type,detail){
    const payload={type,detail,snapshot,error};
    for(const listener of [...listeners]){
      try{listener(payload);}catch(listenerError){console.error('EnergyStore listener error',listenerError);}
    }
  }

  function setSnapshot(nextSnapshot){
    snapshot=nextSnapshot;
    error=null;
    emit('state',nextSnapshot);
  }

  function setError(nextError){
    error=nextError||null;
    emit('error',error);
  }

  function setRefresh(fn){
    refreshFn=typeof fn==='function'?fn:null;
  }

  function subscribe(listener){
    if(typeof listener!=='function') throw new TypeError('EnergyStore.subscribe verwacht een functie');
    listeners.add(listener);
    return ()=>listeners.delete(listener);
  }

  function getState(){return snapshot;}
  function getError(){return error;}
  function refresh(){return refreshFn?refreshFn():Promise.resolve(null);}

  window.EnergyStore={
    getState,
    getError,
    refresh,
    subscribe,
    setSnapshot,
    setError,
    setRefresh
  };
})();
