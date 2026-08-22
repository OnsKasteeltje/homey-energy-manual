(function(){
  'use strict';
  const THRESHOLD=20;
  let lastRaw=null;
  const finite=v=>v!==null&&v!==undefined&&Number.isFinite(Number(v));
  const n=v=>finite(v)?Math.max(0,Number(v)):0;
  const fmt=v=>`${Math.round(n(v)).toLocaleString('nl-NL')} W`;
  const width=v=>n(v)>THRESHOLD?Math.max(3.5,Math.min(8.5,3+n(v)/850)):2;

  function knownPower(load){return load&&finite(load.power_w)?n(load.power_w):0;}
  function titleOf(g){return [...g.querySelectorAll('text')].map(t=>t.textContent?.trim()).find(Boolean)||'';}
  function findCard(layer,title){return [...layer.querySelectorAll('.energy-overig-detail-node')].find(g=>titleOf(g)===title)||null;}
  function setSegment(path,power){if(!path)return;path.style.strokeWidth=String(width(power));path.classList.toggle('is-active',power>THRESHOLD);path.classList.toggle('is-idle',power<=THRESHOLD);}

  function apply(raw){
    const root=document.getElementById('live-energy-flow');
    const r=raw||lastRaw||window.EnergyCoreV2?.state?.raw;
    const fp=window.DishwasherFingerprint?.state;
    const Model=window.LiveEnergyModel;
    const layer=root?.querySelector('.energy-overig-detail-layer');
    if(!root||!r||!Model||!layer)return;
    lastRaw=r;

    const direct=r?.loads?.dishwasher;
    if(direct&&finite(direct.power_w)){
      root.dataset.dishwasherAttribution='CORE_DIRECT';
      root.dataset.dishwasherFingerprintConfidence='1';
      return;
    }
    if(!fp?.active||!finite(fp.power_w)||Number(fp.confidence)<0.68){
      root.dataset.dishwasherAttribution='NONE';
      root.dataset.dishwasherFingerprintConfidence=String(fp?.confidence||0);
      return;
    }

    const vm=Model.buildViewModel(r,true);
    if(!vm)return;
    const dish=n(fp.power_w);
    const loads=r.loads||{};
    const sonos=knownPower(loads.sonos||loads.sonos_kitchen||loads.kitchen_sonos);
    const kitchen=knownPower(loads.kitchen||loads.kitchen_appliances||loads.keukenapparaten);
    const renderedOverig=finite(root.dataset.overigTotalW)?n(root.dataset.overigTotalW):n(vm.other);
    const residual=Math.max(0,renderedOverig-dish-sonos-kitchen);

    const dishCard=findCard(layer,'Vaatwasser');
    if(dishCard){
      const texts=dishCard.querySelectorAll('text');
      if(texts[1])texts[1].textContent=`≈ ${fmt(dish)}`;
      if(texts[2])texts[2].textContent=`actief · fingerprint ${Math.round(Number(fp.confidence)*100)}%`;
      dishCard.classList.add('flow-active');
      dishCard.classList.remove('flow-idle');
    }

    const residualCard=[...layer.querySelectorAll('.energy-overig-detail-node')].find(g=>['Onverdeeld','Overig klein'].includes(titleOf(g)));
    if(residualCard){
      const texts=residualCard.querySelectorAll('text');
      if(texts[1])texts[1].textContent=fmt(residual);
      if(texts[2])texts[2].textContent=residual>THRESHOLD?'rest na geïdentificeerde subcategorieën':'laag / stand-by rest';
      residualCard.classList.toggle('flow-active',residual>THRESHOLD);
      residualCard.classList.toggle('flow-idle',residual<=THRESHOLD);
    }

    const dishBranch=layer.querySelector('.detail-branch-0');
    setSegment(dishBranch,dish);
    if(dishBranch&&dish>THRESHOLD)dishBranch.setAttribute('marker-end','url(#arrow-grid)');

    const residualBranch=layer.querySelector('.detail-branch-3');
    setSegment(residualBranch,residual);
    if(residualBranch){if(residual>THRESHOLD)residualBranch.setAttribute('marker-end','url(#arrow-grid)');else residualBranch.removeAttribute('marker-end');}

    // Horizontale Overig-detailbus: ieder segment krijgt de dikte van het
    // vermogen dat daadwerkelijk door dat segment stroomt. De lange route van
    // Overig naar de vaatwasser draagt dus het vaatwasservermogen (plus eventuele
    // downstream bekende lasten), in plaats van de oorspronkelijke dunne idle-lijn.
    const seg4=layer.querySelector('.detail-seg-4');
    const seg3=layer.querySelector('.detail-seg-3');
    const seg2=layer.querySelector('.detail-seg-2');
    const seg1=layer.querySelector('.detail-seg-1');
    setSegment(seg4,renderedOverig);
    setSegment(seg3,dish+sonos+kitchen);
    setSegment(seg2,dish+sonos);
    setSegment(seg1,dish);

    root.dataset.dishwasherAttribution='P1_FINGERPRINT';
    root.dataset.dishwasherPowerW=String(Math.round(dish));
    root.dataset.dishwasherFingerprintConfidence=String(fp.confidence);
    root.dataset.dishwasherFingerprintVersion=String(fp.version||'');
    root.dataset.overigUnattributedW=String(Math.round(residual));
    root.dataset.overigReconciliationW=String(Math.round(renderedOverig-(dish+sonos+kitchen+residual)));
    root.dataset.overigBusWidthSource='DOWNSTREAM_LOAD';
  }

  function schedule(raw,delay=140){setTimeout(()=>apply(raw),delay);}
  document.addEventListener('energycorev2state',e=>schedule(e.detail?.raw,180));
  document.addEventListener('dishwasherfingerprintstate',()=>schedule(lastRaw,80));
  document.addEventListener('DOMContentLoaded',()=>{schedule(null,900);schedule(null,1700);});
  document.addEventListener('DOMContentSwitch',()=>schedule(null,420));
})();
