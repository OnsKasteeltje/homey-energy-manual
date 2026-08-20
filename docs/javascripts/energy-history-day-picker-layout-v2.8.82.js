(function(){
'use strict';

const ROOT_ID='energy-history-dashboard';

function placeDayPicker(){
  const root=document.getElementById(ROOT_ID);
  if(!root)return;

  const picker=root.querySelector('.eh-day-picker');
  const content=root.querySelector('#eh-content');
  if(!picker||!content)return;

  const activeTab=root.querySelector('.eh-tab.is-active');
  const isDay=!activeTab||activeTab.dataset.mode==='day';

  let row=root.querySelector('.eh-day-summary-row');

  if(!isDay){
    if(row){
      const toolbar=root.querySelector('.eh-toolbar');
      if(toolbar) toolbar.insertBefore(picker,toolbar.querySelector('.eh-period'));
      row.remove();
    }
    picker.hidden=true;
    return;
  }

  picker.hidden=false;

  const cards=content.querySelector('.eh-cards');
  if(!cards)return;

  if(!row){
    row=document.createElement('div');
    row.className='eh-day-summary-row';
  }

  if(cards.parentNode!==row){
    cards.parentNode.insertBefore(row,cards);
    row.appendChild(cards);
  }

  if(picker.parentNode!==row){
    row.appendChild(picker);
  }
}

function schedule(){
  requestAnimationFrame(()=>requestAnimationFrame(placeDayPicker));
}

document.addEventListener('DOMContentLoaded',schedule);
document.addEventListener('click',e=>{
  if(e.target.closest('#energy-history-dashboard .eh-tab')) schedule();
});

const observer=new MutationObserver(schedule);
function observe(){
  const root=document.getElementById(ROOT_ID);
  if(!root){setTimeout(observe,100);return;}
  observer.observe(root,{childList:true,subtree:true});
  schedule();
}
observe();
})();
