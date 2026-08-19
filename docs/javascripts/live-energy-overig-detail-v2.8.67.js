(function(){
  'use strict';
  const SVG='http://www.w3.org/2000/svg';
  const THRESHOLD=20;
  let latestRaw=null;
  const n=v=>Number.isFinite(Number(v))?Math.max(0,Number(v)):0;
  const active=v=>n(v)>THRESHOLD;
  const width=v=>active(v)?Math.max(3.5,Math.min(8.5,3+n(v)/850)):2;
  const fmt=v=>`${Math.round(n(v)).toLocaleString('nl-NL')} W`;
  const known=o=>!!(o&&o.power_w!==null&&o.power_w!==undefined&&Number.isFinite(Number(o.power_w)));
  const pwr=o=>known(o)?n(o.power_w):0;
  const pick=(loads,names)=>{for(const k of names){if(loads&&loads[k]!=null)return loads[k];}return null;};

  function el(tag,attrs={},text=''){
    const x=document.createElementNS(SVG,tag);
    Object.entries(attrs).forEach(([k,v])=>x.setAttribute(k,String(v)));
    if(text)x.textContent=text;
    return x;
  }
  function path(group,d,w,cls,arrow=false){
    const x=el('path',{d,class:`energy-path energy-grid energy-overig-detail-path ${active(w)?'is-active':'is-idle'} ${cls}`});
    x.style.strokeWidth=String(width(w));
    if(arrow&&active(w))x.setAttribute('marker-end','url(#arrow-grid)');
    group.appendChild(x);
  }
  function icon(group,type,cx,cy){
    const g=el('g',{class:`energy-overig-detail-icon icon-${type}`,transform:`translate(${cx} ${cy})`});
    if(type==='quooker'){
      g.appendChild(el('path',{d:'M-18 9 H14 M-14 9 V-5 C-14-15 4-15 4-5 M14 9 V18 M8 18 H20'}));
    }else if(type==='dishwasher'){
      g.appendChild(el('rect',{x:-17,y:-18,width:34,height:36,rx:3}));g.appendChild(el('circle',{cx:0,cy:4,r:10}));g.appendChild(el('path',{d:'M-11-10 H5 M10-10 H12'}));
    }else if(type==='sonos'){
      g.appendChild(el('path',{d:'M-10 14 V-10 L12-15 V8 M-10 2 L12-3'}));g.appendChild(el('circle',{cx:-14,cy:14,r:6}));g.appendChild(el('circle',{cx:8,cy:8,r:6}));
    }else if(type==='kitchen'){
      g.appendChild(el('path',{d:'M-16 4 H16 V15 H-16 Z M-10 4 C-12-4-5-7-7-14 M0 4 C-2-4 5-7 3-14 M10 4 C8-4 15-7 13-14'}));
    }else{
      g.appendChild(el('circle',{cx:-10,cy:0,r:2.7}));g.appendChild(el('circle',{cx:0,cy:0,r:2.7}));g.appendChild(el('circle',{cx:10,cy:0,r:2.7}));
    }
    group.appendChild(g);
  }
  function card(group,x,y,w,h,item){
    const g=el('g',{class:`energy-overig-detail-node ${item.active?'flow-active':'flow-idle'}`});
    g.appendChild(el('rect',{x,y,width:w,height:h,rx:15}));
    icon(g,item.icon,x+w/2,y+31);
    g.appendChild(el('text',{x:x+w/2,y:y+66,'text-anchor':'middle',class:'energy-overig-detail-title'},item.title));
    g.appendChild(el('text',{x:x+w/2,y:y+92,'text-anchor':'middle',class:'energy-overig-detail-value'},item.value));
    g.appendChild(el('text',{x:x+w/2,y:y+113,'text-anchor':'middle',class:'energy-overig-detail-sub'},item.sub));
    group.appendChild(g);
  }
  function setMainPath(svg,cls,w){
    const x=svg.querySelector(`.${cls}`); if(!x)return;
    x.classList.toggle('is-active',active(w));x.classList.toggle('is-idle',!active(w));x.style.strokeWidth=String(width(w));
  }
  function apply(raw){
    const root=document.getElementById('live-energy-flow');
    const svg=root?.querySelector('svg.energy-dashboard.concept-layout');
    const r=raw||latestRaw||window.EnergyCoreV2?.state?.raw;
    if(!svg||!r)return;
    latestRaw=r;
    svg.querySelector('.energy-overig-detail-layer')?.remove();

    const loads=r.loads||{};
    const house=Number.isFinite(Number(r.energy_budget?.house_load_w))?n(r.energy_budget.house_load_w):0;
    const tesla=n(r.tesla?.power_w),boiler=n(r.hot_water?.boiler_power_w);
    const heat=r.quatt||r.heating||{},quatt=n(heat.power_w??heat.quatt_power_w);
    const washer=pwr(loads.washer),dryer=pwr(loads.dryer);
    const overigTotal=Math.max(0,house-tesla-boiler-quatt-washer-dryer);

    const quookerObj=pick(loads,['quooker']);
    const dishwasherObj=pick(loads,['dishwasher']);
    const sonosObj=pick(loads,['sonos','sonos_kitchen','kitchen_sonos']);
    const kitchenObj=pick(loads,['kitchen','kitchen_appliances','keukenapparaten']);
    const quooker=pwr(quookerObj),dishwasher=pwr(dishwasherObj),sonos=pwr(sonosObj),kitchen=pwr(kitchenObj);
    const small=Math.max(0,overigTotal-quooker-dishwasher-sonos-kitchen);

    // Hoofdblok Overig is het totaal van de detailgroep.
    const nodes=[...svg.querySelectorAll('.energy-node')];
    const overigNode=nodes.find(g=>[...g.querySelectorAll('text')].some(t=>t.textContent?.trim()==='Overig'));
    if(overigNode){
      const texts=overigNode.querySelectorAll('text');
      if(texts[1])texts[1].textContent=fmt(overigTotal);
      if(texts[2])texts[2].textContent='detail hieronder';
      overigNode.classList.toggle('flow-active',active(overigTotal));overigNode.classList.toggle('flow-idle',!active(overigTotal));
    }

    // Herbereken de rechter hoofd-bus omdat Overig nu de hele detailgroep omvat.
    const rightOther=active(overigTotal)?overigTotal:0;
    const rightDryer=(active(dryer)?dryer:0)+rightOther;
    const rightWasher=(active(washer)?washer:0)+rightDryer;
    setMainPath(svg,'energy-dryer-to-other',rightOther);
    setMainPath(svg,'energy-washer-to-dryer',rightDryer);
    setMainPath(svg,'energy-right-to-washer',rightWasher);
    const branch=[...svg.querySelectorAll('path.energy-path.energy-grid')].find(p=>(p.getAttribute('d')||'')==='M1350 505 V570');
    if(branch){branch.classList.toggle('is-active',active(overigTotal));branch.classList.toggle('is-idle',!active(overigTotal));branch.style.strokeWidth=String(width(overigTotal));if(active(overigTotal))branch.setAttribute('marker-end','url(#arrow-grid)');else branch.removeAttribute('marker-end');}

    svg.setAttribute('viewBox','0 0 1500 1160');
    const legend=svg.querySelector('.energy-legend'); if(legend)legend.setAttribute('transform','translate(0 280)');
    const rule=svg.querySelector('.energy-rule'); if(rule)rule.setAttribute('y','1140');

    const layer=el('g',{class:'energy-overig-detail-layer'});
    const items=[
      {title:'Quooker',icon:'quooker',obj:quookerObj,power:quooker},
      {title:'Vaatwasser',icon:'dishwasher',obj:dishwasherObj,power:dishwasher},
      {title:'Sonos',icon:'sonos',obj:sonosObj,power:sonos},
      {title:'Keukenapparaten',icon:'kitchen',obj:kitchenObj,power:kitchen},
      {title:'Overig klein',icon:'more',obj:{power_w:small},power:small,residual:true}
    ].map(x=>({...x,active:active(x.power),value:x.residual?fmt(x.power):(known(x.obj)?fmt(x.power):'—'),sub:x.residual?(active(x.power)?'restverbruik':'laag / stand-by'):(known(x.obj)?(active(x.power)?'actief':'laag / stand-by'):'niet gemeten')}));

    const centers=[425,650,875,1100,1325], cardY=855, cardW=190, cardH=130, busY=805;
    const aw=items.map(i=>i.active?i.power:0);
    const remain=[aw.reduce((a,b)=>a+b,0),aw[0]+aw[1]+aw[2]+aw[3],aw[0]+aw[1]+aw[2],aw[0]+aw[1],aw[0]];
    path(layer,'M1350 715 V805',remain[0],'detail-feed',false);
    path(layer,'M1350 805 H1325',remain[0],'detail-seg-5',false);
    path(layer,'M1325 805 H1100',remain[1],'detail-seg-4',false);
    path(layer,'M1100 805 H875',remain[2],'detail-seg-3',false);
    path(layer,'M875 805 H650',remain[3],'detail-seg-2',false);
    path(layer,'M650 805 H425',remain[4],'detail-seg-1',false);
    items.forEach((item,i)=>{path(layer,`M${centers[i]} ${busY} V${cardY}`,item.power,`detail-branch-${i}`,true);card(layer,centers[i]-cardW/2,cardY,cardW,cardH,item);});
    const label=el('text',{x:420,y:780,class:'energy-overig-detail-label'},'Verdieping Overig');layer.appendChild(label);
    svg.appendChild(layer);
  }

  const schedule=raw=>setTimeout(()=>apply(raw),40);
  document.addEventListener('energycorev2state',e=>schedule(e.detail?.raw));
  document.addEventListener('DOMContentLoaded',()=>{setTimeout(()=>apply(),350);setTimeout(()=>apply(),1100);});
  document.addEventListener('DOMContentSwitch',()=>setTimeout(()=>apply(),180));
})();
