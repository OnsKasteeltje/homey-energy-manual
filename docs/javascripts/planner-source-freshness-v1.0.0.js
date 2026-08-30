(() => {
  const refreshSource=()=>{
    const root=document.getElementById('planner-shadow');
    if(!root?.dataset?.source)return;
    try{
      const u=new URL(root.dataset.source,window.location.href);
      u.searchParams.set('_fresh',String(Date.now()));
      root.dataset.source=u.toString();
    }catch(_){/* keep configured source unchanged; planner renderer has its own fallback */}
  };
  refreshSource();
  if(window.document$?.subscribe)window.document$.subscribe(()=>queueMicrotask(refreshSource));
})();
