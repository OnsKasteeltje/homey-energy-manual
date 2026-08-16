(function(){
  const BASE='/homey-energy-manual/data/';
  const localDay=ts=>new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Amsterdam',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(ts));
  const time=ts=>new Date(ts).toLocaleTimeString('nl-NL',{hour:'2-digit',minute:'2-digit'});

  async function getBaseline(){
    const r=await fetch(`${BASE}shadow-baseline-v01.json?ts=${Date.now()}`,{cache:'no-store'});
    if(!r.ok) throw new Error(`shadow-baseline-v01.json: ${r.status}`);
    return r.json();
  }

  function collectEvents(samples){
    const out=[];
    let pw,pd,pb,pt;
    for(const s of samples){
      if(typeof s.washerActive==='boolean' && s.washerActive!==pw){
        if(pw!==undefined) out.push({ts:s.ts,text:`Wasmachine ${s.washerActive?'gestart':'klaar'}`});
        pw=s.washerActive;
      }
      if(typeof s.dryerActive==='boolean' && s.dryerActive!==pd){
        if(pd!==undefined) out.push({ts:s.ts,text:`Droger ${s.dryerActive?'gestart':'klaar'}`});
        pd=s.dryerActive;
      }
      if(s.boilerState && s.boilerState!==pb){
        if(pb!==undefined && ['VERWARMEN','OP_TEMPERATUUR'].includes(s.boilerState)){
          out.push({ts:s.ts,text:`Boiler ${s.boilerState==='VERWARMEN'?'verwarmt':'op temperatuur'}`});
        }
        pb=s.boilerState;
      }

      // Werkelijk Tesla-laden: laadstatus heeft voorrang; >250 W is fallback voor oudere samples.
      const hasState=typeof s.chargeState==='string' && s.chargeState.length>0;
      const charging=hasState ? s.chargeState==='plugged_in_charging' : Number(s.teslaW||0)>250;
      if(charging!==pt){
        if(pt!==undefined) out.push({ts:s.ts,text:charging?'Tesla laden gestart':'Tesla laden gestopt'});
        pt=charging;
      }
    }
    return out.sort((a,b)=>new Date(a.ts)-new Date(b.ts)).slice(-12);
  }

  async function enhance(){
    const timeline=document.querySelector('#energy-history-dashboard .eh-timeline');
    if(!timeline) return;
    try{
      const base=await getBaseline();
      const today=localDay(Date.now());
      const samples=(base.samples||[]).filter(s=>localDay(s.ts)===today);
      const ev=collectEvents(samples);
      timeline.innerHTML=ev.length
        ? ev.map(e=>`<div class="eh-event"><span class="eh-time">${time(e.ts)}</span><span>${e.text}</span></div>`).join('')
        : '<div class="eh-empty">Nog geen herkenbare statusovergangen in de huidige baseline.</div>';
    }catch(_e){}
  }

  function start(){
    enhance();
    const root=document.getElementById('energy-history-dashboard');
    if(!root) return;
    let timer;
    new MutationObserver(()=>{
      clearTimeout(timer);
      timer=setTimeout(enhance,80);
    }).observe(root,{childList:true,subtree:true});
  }

  document.addEventListener('DOMContentLoaded',start);
  document.addEventListener('DOMContentSwitch',start);
})();
