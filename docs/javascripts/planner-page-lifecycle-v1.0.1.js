(() => {
  const ROOT_ID='planner-shadow';
  const loaded=new WeakSet();
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const loadScript=src=>new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=src;s.async=false;s.onload=()=>resolve();s.onerror=()=>reject(new Error(`load failed: ${src}`));document.head.append(s);});
  const hasRendered=root=>!root.querySelector('#ps-status')&&!!root.querySelector('.ps-summary, .ps-section');
  const waitRendered=async(root,timeout=1200)=>{const end=Date.now()+timeout;while(Date.now()<end){if(hasRendered(root))return true;await sleep(100);}return hasRendered(root);};
  const ensureBoilerRow=root=>{
    const section=[...root.querySelectorAll('.ps-section')].find(s=>s.querySelector('h2')?.textContent?.trim()==='Prijs & planneracties');
    if(!section)return;
    const rows=[...section.querySelectorAll('.ps-action-row')];
    if(rows.some(r=>r.querySelector('.ps-action-name')?.textContent?.trim()==='Boiler'))return;
    const row=document.createElement('div');row.className='ps-action-row';
    const name=document.createElement('div');name.className='ps-action-name';name.textContent='Boiler';
    const track=document.createElement('div');track.className='ps-action-track';
    const empty=document.createElement('div');empty.className='ps-action-segment ps-action-empty';empty.style.gridColumn='1 / 97';
    const wwCard=[...root.querySelectorAll('.ps-card')].find(c=>c.querySelector('.ps-card-title')?.textContent?.trim()==='Warm water');
    const status=wwCard?.querySelector('.ps-card-value')?.textContent?.trim();
    empty.textContent=status==='Dagdoel gehaald'?'geen planning · dagdoel gehaald':'geen warmwaterplanning in deze horizon';
    track.append(empty);row.append(name,track);section.append(row);
  };
  const boot=async root=>{
    if(!root||loaded.has(root))return;loaded.add(root);
    try{
      if(!hasRendered(root)){
        // On a direct page load the bundled renderer may already be fetching.
        // Give it a short chance to finish; after instant navigation there is
        // no renderer, so fall back to a fresh standalone initialization.
        let ok=await waitRendered(root,1200);
        if(!ok){
          await loadScript('../javascripts/planner-shadow.js?lifecycle=2');
          ok=await waitRendered(root,8000);
        }
        if(!ok){loaded.delete(root);return;}
      }
      ensureBoilerRow(root);
      await loadScript('../javascripts/planner-axes-v1.1.0.js?lifecycle=2').catch(()=>{});
      await loadScript('../javascripts/planner-ww-multislot-v1.0.0.js?lifecycle=2').catch(()=>{});
      await loadScript('../javascripts/planner-device-tabs-v1.0.2.js?lifecycle=2').catch(()=>{});
      ensureBoilerRow(root);
    }catch(e){loaded.delete(root);console.warn('Planner lifecycle init failed',e);}
  };
  const bootCurrent=()=>boot(document.getElementById(ROOT_ID));
  const observer=new MutationObserver(mutations=>{for(const m of mutations)for(const n of m.addedNodes){if(!(n instanceof Element))continue;const root=n.id===ROOT_ID?n:n.querySelector?.(`#${ROOT_ID}`);if(root)boot(root);}});
  const startObserver=()=>{observer.observe(document.body,{childList:true,subtree:true});bootCurrent();};
  if(document.body)startObserver();else addEventListener('DOMContentLoaded',startObserver,{once:true});
  // MkDocs Material instant-navigation lifecycle. This is the authoritative
  // hook when available; MutationObserver remains as a browser-only fallback.
  if(window.document$?.subscribe)window.document$.subscribe(()=>queueMicrotask(bootCurrent));
})();