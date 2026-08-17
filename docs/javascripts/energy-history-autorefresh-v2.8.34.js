(function(){
  'use strict';
  const INTERVAL=5*60*1000;
  let timer=null;
  function refresh(){if(document.hidden)return;if(document.getElementById('energy-history-dashboard'))document.dispatchEvent(new Event('DOMContentSwitch'));}
  function start(){if(timer)clearInterval(timer);timer=setInterval(refresh,INTERVAL);}
  document.addEventListener('DOMContentLoaded',start);
})();
