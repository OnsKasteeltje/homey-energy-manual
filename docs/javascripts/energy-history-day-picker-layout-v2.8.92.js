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

  [...row.children].forEach(child=>{
    if(child.classList?.contains('eh-cards') && child!==cards) child.remove();
  });

  if(cards.parentNode!==row) row.insertBefore(cards,picker.parentNode===row?picker:null);
  if(picker.parentNode!==row) row.appendChild(picker);

  if(row.firstElementChild!==cards) row.insertBefore(cards,row.firstElementChild);
  if(cards.nextElementSibling!==picker) row.insertBefore(picker,cards.nextElementSibling);

  return picker.parentNode===row && cards.parentNode===row && row.querySelectorAll(':scope > .eh-cards').length===1;
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

// The history renderer replaces #eh-content when another day is selected.
// Because the visual day picker is normally moved into that content subtree,
// it would be deleted together with the old KPI cards. Move it back to the
// persistent toolbar in the capture phase, before the renderer handles the
// change event, and move it beside the newly rendered KPI cards afterwards.
document.addEventListener('change',e=>{
  if(!e.target.matches(`#${ROOT_ID} #eh-day-select`)) return;
  const root=document.getElementById(ROOT_ID);
  const picker=root?.querySelector('.eh-day-picker');
  if(root&&picker) restoreToolbar(root,picker);
},true);

document.addEventListener('DOMContentLoaded',schedule);
document.addEventListener('click',e=>{
  if(e.target.closest(`#${ROOT_ID} .eh-tab`)) schedule();
});
document.addEventListener('change',e=>{
  if(e.target.matches(`#${ROOT_ID} #eh-day-select`)) schedule();
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
