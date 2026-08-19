(function(){
  'use strict';

  const SVG_NS='http://www.w3.org/2000/svg';

  function applyGridBatteryLink(){
    const root=document.getElementById('live-energy-flow');
    const svg=root?.querySelector('svg.energy-svg');
    if(!root||!svg)return;

    svg.querySelectorAll('.energy-grid-battery-link,.energy-grid-battery-label').forEach(el=>el.remove());
    root.querySelectorAll('.energy-topology-note').forEach(el=>el.remove());

    const gridRect=svg.querySelector('.energy-node.grid rect');
    const batteryRect=svg.querySelector('.energy-node.battery rect');
    if(!gridRect||!batteryRect)return;

    const gx=Number(gridRect.getAttribute('x'));
    const gy=Number(gridRect.getAttribute('y'));
    const gw=Number(gridRect.getAttribute('width'));
    const gh=Number(gridRect.getAttribute('height'));
    const bx=Number(batteryRect.getAttribute('x'));
    const by=Number(batteryRect.getAttribute('y'));
    const bw=Number(batteryRect.getAttribute('width'));
    const bh=Number(batteryRect.getAttribute('height'));

    const y=Math.min(gy,by)-34;
    const startX=gx+gw;
    const endX=bx;
    const centerX=(startX+endX)/2;

    let defs=svg.querySelector('defs');
    if(!defs){
      defs=document.createElementNS(SVG_NS,'defs');
      svg.insertBefore(defs,svg.firstChild);
    }

    if(!svg.querySelector('#arrow-topology')){
      const marker=document.createElementNS(SVG_NS,'marker');
      marker.setAttribute('id','arrow-topology');
      marker.setAttribute('markerWidth','9');
      marker.setAttribute('markerHeight','9');
      marker.setAttribute('refX','8');
      marker.setAttribute('refY','4');
      marker.setAttribute('orient','auto');
      const arrow=document.createElementNS(SVG_NS,'path');
      arrow.setAttribute('d','M0,0 L0,8 L8,4 z');
      arrow.setAttribute('class','arrow-topology');
      marker.appendChild(arrow);
      defs.appendChild(marker);
    }

    const link=document.createElementNS(SVG_NS,'path');
    link.setAttribute('class','energy-grid-battery-link');
    link.setAttribute('d',`M${startX} ${gy+gh/2} V${y} H${endX} V${by+bh/2}`);
    link.setAttribute('marker-end','url(#arrow-topology)');
    link.setAttribute('aria-label','Elektrische verbinding tussen net en batterij via de AC-bus');
    svg.appendChild(link);

    const label=document.createElementNS(SVG_NS,'text');
    label.setAttribute('class','energy-grid-battery-label');
    label.setAttribute('x',String(centerX));
    label.setAttribute('y',String(y-10));
    label.setAttribute('text-anchor','middle');
    label.textContent='Net ↔ accu via AC-bus';
    svg.appendChild(label);

    const note=document.createElement('div');
    note.className='energy-topology-note';
    note.innerHTML='<strong>Net ↔ accu:</strong> de batterij is elektrisch met het net verbonden via de AC-bus van de woning. Deze pijl toont de fysieke/topologische verbinding; hij is <strong>geen extra gemeten energiestroom</strong> en wordt niet dubbel meegeteld in de energiebalans.';
    svg.insertAdjacentElement('afterend',note);
  }

  function schedule(){setTimeout(applyGridBatteryLink,60);}

  document.addEventListener('DOMContentLoaded',schedule);
  document.addEventListener('DOMContentSwitch',schedule);
  document.addEventListener('energycorev2state',schedule);
  setTimeout(applyGridBatteryLink,900);
})();
