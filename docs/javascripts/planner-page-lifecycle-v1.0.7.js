(() => {
  const ROOT_ID='planner-shadow';
  const ready=new WeakSet();
  const running=new WeakSet();
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const loadScript=src=>new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=src;s.async=false;s.onload=()=>resolve();s.onerror=()=>reject(new Error(`load failed: ${src}`));document.head.append(s);});
  const hasRendered=root=>!root.querySelector('#ps-status')&&!!root.querySelector('.ps-summary, .ps-section');
  const waitRendered=async(root,timeout=1200)=>{const end=Date.now()+timeout;while(Date.now()<end){if(hasRendered(root))return true;await sleep(100);}return hasRendered(root);};
  const boot=async root=>{
    if(!root||running.has(root))return;
    if(ready.has(root)&&hasRendered(root))return;
    if(!hasRendered(root))ready.delete(root);
    running.add(root);
    try{
      if(!hasRendered(root)){
        let ok=await waitRendered(root,1200);
        if(!ok){await loadScript('../javascripts/planner-shadow.js?lifecycle=7');ok=await waitRendered(root,8000);}
        if(!ok)return;
      }
      ready.add(root);
      await loadScript('../javascripts/planner-axes-v1.1.0.js?lifecycle=7').catch(()=>{});
      await loadScript('../javascripts/planner-ww-multislot-v1.0.0.js?lifecycle=7').catch(()=>{});
      await loadScript('../javascripts/planner-flex-energy-v1.0.0.js?lifecycle=7').catch(()=>{});
      await loadScript('../javascripts/planner-action-details-v1.0.1.js?lifecycle=7').catch(()=>{});
      await loadScript('../javascripts/planner-device-tabs-v1.0.3.js?lifecycle=7').catch(()=>{});
    }catch(e){ready.delete(root);console.warn('Planner lifecycle init failed',e);}
    finally{running.delete(root);}
  };
  const bootCurrent=()=>boot(document.getElementById(ROOT_ID));
  const observer=new MutationObserver(()=>queueMicrotask(bootCurrent));
  const startObserver=()=>{observer.observe(document.body,{childList:true,subtree:true});bootCurrent();};
  if(document.body)startObserver();else addEventListener('DOMContentLoaded',startObserver,{once:true});
  if(window.document$?.subscribe)window.document$.subscribe(()=>queueMicrotask(bootCurrent));
})();