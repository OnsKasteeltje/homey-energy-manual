(() => {
  const ROOT_ID='planner-shadow';
  const MOVED_ID='ps-forecast-load-windows';
  let timer=null;

  const sectionByTitle=(root,title)=>[...root.querySelectorAll(':scope > section.ps-section')]
    .find(s=>s.querySelector(':scope > h2')?.textContent.trim()===title)||null;

  function moveForecastRows(){
    const root=document.getElementById(ROOT_ID);if(!root)return;
    const balanceSection=sectionByTitle(root,'24-uurs energiebalans');
    const priceSection=sectionByTitle(root,'Prijs & planneracties');
    if(!balanceSection||!priceSection)return;

    const rows=[...priceSection.querySelectorAll(':scope > .ps-action-row')];
    let target=document.getElementById(MOVED_ID);
    if(!target&&!rows.length)return;

    if(!target){
      target=document.createElement('section');
      target.id=MOVED_ID;
      target.className='ps-section ps-forecast-load-windows';
    }

    // Requested order is literal: first the complete 24h PV energy-balance graph,
    // immediately followed by the load-window timelines, and only then prices.
    balanceSection.after(target);
    rows.forEach(row=>target.append(row));

    // WW enhancement renders its legend/detail immediately after the Boiler plan row.
    // Keep that material with the moved timelines instead of leaving it under prices.
    const wwDetail=priceSection.querySelector(':scope > #ps-ww-inline-detail');
    if(wwDetail)target.append(wwDetail);
  }

  function schedule(){
    clearTimeout(timer);
    // Planner lifecycle enrichers (labels + WW multislot) must first finish while
    // the rows are still in their native price section. Reorder only afterwards.
    timer=setTimeout(moveForecastRows,2200);
  }

  function install(){
    const root=document.getElementById(ROOT_ID);if(!root)return;
    schedule();
    if(root.dataset.forecastTimelineOrderObserver==='3')return;
    root.dataset.forecastTimelineOrderObserver='3';
    const observer=new MutationObserver(schedule);
    observer.observe(root,{childList:true,subtree:true});
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();
  if(window.document$?.subscribe)window.document$.subscribe(install);
})();
