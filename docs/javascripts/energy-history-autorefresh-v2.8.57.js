(function(){
'use strict';
const INTERVAL=300000;
let timer=null;
function refresh(){
  if(document.hidden)return;
  if(document.getElementById('energy-history-dashboard')) document.dispatchEvent(new Event('DOMContentSwitch'));
}
function start(){
  if(timer)clearInterval(timer);
  refresh();
  timer=setInterval(refresh,INTERVAL);
}
document.addEventListener('DOMContentLoaded',start);
document.addEventListener('visibilitychange',function(){if(!document.hidden)refresh();});
window.addEventListener('pageshow',refresh);
window.addEventListener('focus',refresh);
})();
