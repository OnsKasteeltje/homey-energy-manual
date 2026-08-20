(function(){
'use strict';

const ROOT_ID='energy-history-dashboard';
let retryTimer=null;

function isDayMode(root){
  const active=root.querySelector('.eh-tab.is-active');
  return !active || active.dataset.mode==='day';
}

function restoreToolbar(root,picker){
  const toolbar=root.querySelector('.eh-toolbar');
  if(!toolbar || !picker) return;
  const period=toolbar.querySelector('.eh-period');
  if(picker.parentNode!==toolbar){
    if(period) toolbar.insertBefore(picker,period);
    else toolbar.appendChild(picker);
  }
}

function placeDayPicker(){
  const root=document.getElementById(ROOT_ID);
  if(!root) return false;

  const picker=root.querySelector('.eh-day-picker');
  const content=root.querySelector('#eh-content');
  if(!picker || !content) return false;

  let row=root.querySelector('.eh-day-summary-row');

  if(!isDayMode(root)){
    picker.hidden=true;
    if(row){
      restoreToolbar(root,picker);
      row.remove();
    }
    return true;
  }

  const cards=content.querySelector('.eh-cards');
  if(!cards) return false;

  picker.hidden=false;

  if(!row){
    row=document.createElement('div');
    row.className='eh-day-summary-row';
    cards.parentNode.insertBefore(row,cards);
  }

  if(cards.parentNode!==row) row.appendChild(cards);
  if(picker.parentNode!==row) row.appendChild(picker);

  return picker.parentNode===row && cards.parentNode===row;
}

function retryPlacement(){
  let tries=0;
  if(retryTimer) clearInterval(retryTimer);
  retryTimer=setInterval(()=>{
    tries++;
    if(placeDayPicker() || tries>=40){
      clearInterval(retryTimer);
      retryTimer=null;
    }
  },250);
}

function schedule(){
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
    if(!placeDayPicker()) retryPlacement();
  }));
}

document.addEventListener('DOMContentLoaded',schedule);
document.addEventListener('click',e=>{
  if(e.target.closest('#energy-history-dashboard .eh-tab')) schedule();
});
window.addEventListener('pageshow',schedule);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)schedule();});

const observer=new MutationObserver(schedule);
function startObserver(){
  const root=document.getElementById(ROOT_ID);
  if(!root){setTimeout(startObserver,100);return;}
  observer.observe(root,{childList:true,subtree:true});
  schedule();
}
startObserver();
})();
