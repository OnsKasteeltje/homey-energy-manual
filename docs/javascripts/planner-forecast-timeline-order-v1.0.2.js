(() => {
  const ROOT_ID='planner-shadow';
  const MOVED_ID='ps-forecast-load-windows';
  let moving=false;

  const sectionByTitle=(root,title)=>[...root.querySelectorAll(':scope > section.ps-section')]
    .find(s=>s.querySelector(':scope > h2')?.textContent.trim()===title)||null;

  const labelRows=target=>{
    const aliases={Tesla:'Tesla plan','Tesla plan':'Tesla plan',Boiler:'Boiler plan','Boiler plan':'Boiler plan',Accu:'Accu plan','Accu plan':'Accu plan'};
    target.querySelectorAll(':scope > .ps-action-row').forEach(row=>{
      const name=row.querySelector('.ps-action-name');
      const current=name?.textContent?.trim();
      if(name&&aliases[current])name.textContent=aliases[current];
      row.classList.add('ps-forecast-row');
    });
    if(!document.getElementById('ps-forecast-label-style')){
      const style=document.createElement('style');
      style.id='ps-forecast-label-style';
      style.textContent=`
        #planner-shadow .ps-forecast-row .ps-action-name::after{content:' forecast';display:block;font-size:.58em;font-weight:500;opacity:.65;line-height:1.05}
        #planner-shadow .ps-forecast-row .ps-action-segment{outline:1px dashed color-mix(in srgb,currentColor 45%,transparent);outline-offset:-2px}
      `;
      document.head.append(style);
    }
  };

  function moveForecastRows(){
    if(moving)return;
    const root=document.getElementById(ROOT_ID);if(!root)return;
    const balanceSection=sectionByTitle(root,'24-uurs energiebalans');
    const priceSection=sectionByTitle(root,'Prijs & planneracties');
    if(!balanceSection||!priceSection)return;

    const rows=[...priceSection.querySelectorAll(':scope > .ps-action-row')];
    let target=document.getElementById(MOVED_ID);
    if(!target&&!rows.length)return;

    moving=true;
    try{
      if(!target){
        target=document.createElement('section');
        target.id=MOVED_ID;
        target.className='ps-section ps-forecast-load-windows';
      }
      if(target.parentElement!==root||target.previousElementSibling!==balanceSection)balanceSection.after(target);
      rows.forEach(row=>target.append(row));
      const wwDetail=priceSection.querySelector(':scope > #ps-ww-inline-detail');
      if(wwDetail)target.append(wwDetail);
      labelRows(target);
    }finally{moving=false;}
  }

  function install(){
    const root=document.getElementById(ROOT_ID);if(!root)return;
    moveForecastRows();
    if(root.dataset.forecastTimelineOrderObserver==='4')return;
    root.dataset.forecastTimelineOrderObserver='4';
    const observer=new MutationObserver(()=>queueMicrotask(moveForecastRows));
    observer.observe(root,{childList:true,subtree:true});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();
  if(window.document$?.subscribe)window.document$.subscribe(install);
})();
