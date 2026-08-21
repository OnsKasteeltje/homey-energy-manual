(function(){
'use strict';

const ROOT_ID='energy-history-dashboard';
let retryTimer=null;

function isDayMode(root){
  const active=root.querySelector('.eh-tab.is-active');
  return !active || active.dataset.mode==='day';
}

function ensurePersistentRow(root){
  const shell=root.querySelector('.eh-shell');
  const content=root.querySelector('#eh-content');
  if(!shell||!content) return null;
  let row=root.querySelector('.eh-day-summary-row');
  if(!row){
    row=document.createElement('div');
    row.className='eh-day-summary-row';
    shell.insertBefore(row,content);
  }
  return row;
}

function restoreToolbar(root,picker){
  const toolbar=root.querySelector('.eh-toolbar');
  if(!toolbar||!picker) return;
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
  if(!picker||!content) return false;

  if(!isDayMode(root)){
    picker.hidden=true;
    restoreToolbar(root,picker);
    root.querySelector('.eh-day-summary-row')?.remove();
    return true;
  }

  const cards=content.querySelector(':scope > .eh-cards');
  if(!cards) return false;
  const row=ensurePersistentRow(root);
  if(!row) return false;

  picker.hidden=false;
  // Keep the selector outside #eh-content: draw() may replace content.innerHTML.
  if(picker.parentNode!==row) row.appendChild(picker);
  // KPI cards are freshly rendered each draw; move only those into the persistent row.
  [...row.querySelectorAll(':scope > .eh-cards')].forEach(old=>{if(old!==cards)old.remove();});
  row.insertBefore(cards,picker);

  return picker.parentNode===row && cards.parentNode===row && !content.contains(picker);
}

function retryPlacement(){
  let tries=0;
  if(retryTimer) clearInterval(retryTimer);
  retryTimer=setInterval(()=>{
    tries++;
    if(placeDayPicker()||tries>=40){clearInterval(retryTimer);retryTimer=null;}
  },250);
}
function schedule(){requestAnimationFrame(()=>requestAnimationFrame(()=>{if(!placeDayPicker())retryPlacement();}));}

document.addEventListener('DOMContentLoaded',schedule);
document.addEventListener('click',e=>{if(e.target.closest(`#${ROOT_ID} .eh-tab`))schedule();});
document.addEventListener('change',e=>{if(e.target.matches(`#${ROOT_ID} #eh-day-select`))schedule();});
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
