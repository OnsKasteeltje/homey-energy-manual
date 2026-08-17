(function(){
  const RUNTIME='/homey-energy-manual/data/tesla-runtime.json',STATUS='/homey-energy-manual/data/homey-status.json';
  const LABELS={GEEN_DEADLINE:'Opportunistisch',WACHT_OP_PV:'Wacht op PV',OPPORTUNISTISCH:'Opportunistisch laden',DEADLINE_WACHT:'Wacht op geschikt laadmoment',DEADLINE_CATCH_UP:'Catch-up actief',DEADLINE_GEMIST_CATCH_UP:'Deadline gepasseerd · catch-up',DEADLINE_PRIJS_NEGATIEF:'Laden · negatieve stroomprijs',DEADLINE_PV_OVERSCHOT:'Laden op PV-overschot',DEADLINE_PV_FORECAST:'Laden · gunstig PV-forecastuur',DEADLINE_PRIJS_GOEDKOOP:'Laden · gunstige stroomprijs',DEADLINE_WACHT_GOEDKOPER:'Wacht op goedkoper laadmoment',DEADLINE_EQUALIZER_BLOKKEERT:'Equalizer blokkeert laden',DEADLINE_ONDER_DRUK_EQUALIZER:'Deadline onder druk door Equalizer',DEADLINE_NIET_HAALBAAR_EQUALIZER:'Deadline niet haalbaar door Equalizer',DEADLINE_LADEN_GEBLOKKEERD:'Laden geblokkeerd',DEADLINE_ONDER_DRUK_GEBLOKKEERD:'Deadline onder druk · laden geblokkeerd',DEADLINE_NIET_HAALBAAR_GEBLOKKEERD:'Deadline niet haalbaar · laden geblokkeerd',DOEL_GEHAALD:'Laaddoel gehaald',NIET_AANGESLOTEN:'Tesla niet aangesloten',CONFIG_FOUT:'Deadlineconfiguratie fout',BASELINE_FOUT:'Meetbaseline ontbreekt',KALIBRATIE_AFWIJKING:'Kalibratie/meetafwijking'};
  const LEGACY_AUDIT=new Set(['KALIBRATIE_AFWIJKING','BASELINE_FOUT','CONFIG_FOUT']);
  async function json(url){try{const r=await fetch(`${url}?ts=${Date.now()}`,{cache:'no-store'});return r.ok?await r.json():null;}catch(e){return null;}}
  function currentV2Tesla(){
    const raw=window.EnergyCoreV2?.state?.raw;
    const t=raw?.tesla||{};
    return {
      available:!!raw,
      connected:t.connected===true,
      charging:t.charging===true||Number(t.power_w||0)>300,
      powerW:Number(t.power_w||0),
      need:String(t.need||raw?.manager?.decision||'HOLD')
    };
  }
  function applyCurrentV2(g){
    const v2=currentV2Tesla();if(!v2.available)return false;
    const state=g.querySelector('.ha-goal-state'),sub=g.querySelector('small');
    if(state){
      state.textContent=v2.charging?`Laadt nu${v2.powerW?` · ${(v2.powerW/1000).toLocaleString('nl-NL',{maximumFractionDigits:2})} kW`:''}`:v2.connected?'Aangesloten · wacht op opportunity':'Niet aangesloten';
      state.className=`ha-goal-state ${v2.charging?'ok':v2.connected?'warn':'off'}`;
    }
    if(sub)sub.textContent=v2.charging?'Actuele Energy Core v2-laadstatus':v2.connected?`${v2.need} · wacht op gunstig laadmoment`:'Geen actieve laadopdracht';
    return true;
  }
  async function apply(){
    const [d,s]=await Promise.all([json(RUNTIME),json(STATUS)]);
    if(!d&&!s)return;
    if(s){
      const tes=(s.flows||[]).find(f=>/^Tesla laden v2\./.test(f.name)&&f.enabled&&!f.broken)||(s.flows||[]).find(f=>f.category==='Tesla'&&f.enabled&&!f.broken);
      document.querySelectorAll('.ha-stage.control .ha-row').forEach(row=>{const spans=row.querySelectorAll(':scope > span');if(spans.length<2||!['Tesla / Easee','Tesla'].includes(spans[0].textContent.trim()))return;spans[1].innerHTML=tes?`${tes.name} · Equalizer beveiliging actief <span class="dot ok"></span>`:'v2 Control nog SHADOW <span class="dot off"></span>';});
    }
    const g=[...document.querySelectorAll('.ha-stage.decision .ha-goal')].find(x=>x.querySelector('strong')?.textContent.trim()==='Tesla laden');if(!g)return;
    if(!d){applyCurrentV2(g);return;}
    const status=String(d.status||'').toUpperCase();
    // Legacy auditresultaten uit een oude laad-/SOC-sessie mogen de actuele v2-toestand niet domineren.
    if(LEGACY_AUDIT.has(status)){applyCurrentV2(g);return;}
    const state=g.querySelector('.ha-goal-state'),sub=g.querySelector('small'),label=LABELS[status]||d.status||'';
    if(state&&label){state.textContent=label;state.className=`ha-goal-state ${/laden|catch-up|gehaald/i.test(label)&&!/blokkeerd|blokkeert|onder druk|niet haalbaar|afwijking|ontbreekt/i.test(label)?'ok':'warn'}`;}
    if(sub){const eq=d.equalizer||d.decision?.equalizer||{},req=Math.max(0,Number(eq.requestedA??d.targetA??0)),act=Number(eq.actualA??0),mode=String(eq.mode||'').toLowerCase(),maxA=Number(eq.maxPhaseA);if(mode==='blocked')sub.textContent=`Equalizer blokkeert · ${req.toFixed(0)} A gevraagd → 0 A werkelijk · max. netfase ${Number.isFinite(maxA)?maxA.toFixed(0)+' A':'onbekend'}`;else if(mode==='blocked_unknown')sub.textContent=`Laden geblokkeerd · ${req.toFixed(0)} A gevraagd → 0 A werkelijk · geen bewijs voor Equalizer`;else if(mode==='zero_pending')sub.textContent=`Laden nog niet gestart · ${req.toFixed(0)} A gevraagd → 0 A werkelijk · oorzaak wordt vastgesteld`;else if(mode==='limited')sub.textContent=`Equalizer begrenst · ${req.toFixed(0)} A gevraagd → ~${act.toFixed(1)} A werkelijk`;else {const charging=String(d.chargeState||'').toLowerCase().includes('charging')||Number(d.teslaW||0)>500;sub.textContent=charging?`Equalizer begrenst niet · ${req.toFixed(0)} A gevraagd → ~${act.toFixed(1)} A werkelijk`:'Tesla laadt niet · geen actieve Equalizer-begrenzing vastgesteld';}}
  }
  function start(){apply();setInterval(apply,20000);}document.addEventListener('DOMContentLoaded',start);document.addEventListener('DOMContentSwitch',apply);document.addEventListener('energycorev2state',()=>setTimeout(apply,50));
})();
