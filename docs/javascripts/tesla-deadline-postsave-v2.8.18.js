(function(){
  const BASE='/homey-energy-manual/data/';
  async function getCommand(){
    try{
      const r=await fetch(`${BASE}tesla-deadline-command.json?ts=${Date.now()}`,{cache:'no-store'});
      if(!r.ok)return null;
      return r.json();
    }catch(_e){return null;}
  }
  function hasValidSocCommand(c){
    const a=Number(c?.currentSoc),b=Number(c?.targetSoc);
    return c?.active===true && Number.isFinite(a) && Number.isFinite(b) && b>a;
  }
  function rebuildRuntime(panel,c){
    const runtime=panel?.querySelector('.tesla-deadline-runtime');
    if(!runtime||!hasValidSocCommand(c))return;
    runtime.classList.remove('tesla-deadline-runtime--migration');
    runtime.hidden=false;
    runtime.innerHTML=`<div><span>Status</span><strong>Status wordt door Homey verwerkt</strong></div><div><span>SOC-doel</span><strong>${Number(c.currentSoc)}% → ${Number(c.targetSoc)}%</strong></div><div><span>Uiterlijk starten</span><strong>—</strong></div>`;
    const note=panel.querySelector('.tesla-deadline-note');
    if(note) note.textContent=`Deadline actief. SOC ingevoerd ${new Date(c.socEnteredAt||c.requestedAt).toLocaleString('nl-NL')}. De operationele status en het uiterste startmoment volgen zodra Homey deze publiceert.`;
  }
  async function refreshAfterSave(){
    for(let i=0;i<8;i++){
      await new Promise(r=>setTimeout(r,i?750:150));
      const c=await getCommand();
      if(hasValidSocCommand(c)){
        rebuildRuntime(document.getElementById('tesla-deadline-control'),c);
        return;
      }
    }
  }
  function wire(){
    const panel=document.getElementById('tesla-deadline-control');
    if(!panel||panel.dataset.postsaveWired)return;
    panel.dataset.postsaveWired='1';
    panel.addEventListener('click',e=>{
      if(e.target.closest('.tesla-deadline-save')) refreshAfterSave();
    });
  }
  function start(){
    wire();
    const root=document.getElementById('live-energy-flow')||document.body;
    new MutationObserver(wire).observe(root,{childList:true,subtree:true});
    getCommand().then(c=>{if(hasValidSocCommand(c)) rebuildRuntime(document.getElementById('tesla-deadline-control'),c);});
  }
  document.addEventListener('DOMContentLoaded',start);
  document.addEventListener('DOMContentSwitch',start);
})();
