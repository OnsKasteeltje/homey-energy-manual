(() => {
  const root=document.getElementById('planner-shadow');
  if(!root)return;

  const nlNumber=s=>Number(String(s).replace(/\./g,'').replace(',','.'));
  const fmtKw=w=>`${(Number(w)/1000).toLocaleString('nl-NL',{minimumFractionDigits:0,maximumFractionDigits:1})} kW`;
  const fmtPrice=v=>`€ ${Number(v).toLocaleString('nl-NL',{minimumFractionDigits:2,maximumFractionDigits:3})}`;

  function balanceValues(chart){
    const vals=[];
    chart.querySelectorAll('.ps-bar[title]').forEach(bar=>{
      const m=bar.title.match(/(-?[\d.,]+)\s*W\b/);
      if(!m)return;
      const n=nlNumber(m[1]);
      if(Number.isFinite(n))vals.push(Math.abs(n));
    });
    return vals;
  }

  function priceValues(chart){
    const vals=[];
    chart.querySelectorAll('.ps-price-bar[title]').forEach(bar=>{
      const m=bar.title.match(/€\s*(-?[\d.,]+)\/kWh/);
      if(!m)return;
      const n=nlNumber(m[1]);
      if(Number.isFinite(n))vals.push(n);
    });
    return vals;
  }

  function makeAxis(kind,labels,positions){
    const axis=document.createElement('div');
    axis.className=`ps-y-axis ps-y-axis-${kind}`;
    labels.forEach((text,i)=>{
      const lab=document.createElement('span');
      lab.className='ps-y-axis-label';
      lab.style.top=`${positions[i]}%`;
      lab.textContent=text;
      axis.append(lab);
    });
    return axis;
  }

  function wrapChart(chart,kind,axis){
    if(chart.closest(`.ps-axis-wrap-${kind}`))return;
    const wrap=document.createElement('div');
    wrap.className=`ps-axis-wrap ps-axis-wrap-${kind}`;
    chart.parentNode.insertBefore(wrap,chart);
    wrap.append(axis,chart);
  }

  function decorateBalance(chart){
    if(chart.dataset.axesV110==='1')return;
    const vals=balanceValues(chart);
    const max=Math.max(1000,...vals);
    const axis=makeAxis('balance',[fmtKw(max),fmtKw(max/2),'0 kW',fmtKw(-max/2),fmtKw(-max)],[2,26,50,74,98]);
    wrapChart(chart,'balance',axis);
    chart.dataset.axesV110='1';
    const note=chart.closest('.ps-section')?.querySelector('.ps-chart-note');
    if(note)note.textContent='Verwachting vóór flexibele lasten. Y-as = vermogen in kW. 0 kW is de middenlijn: blauw boven nul = netimport; groen onder nul = PV-overschot/export. Hover op base load voor de historische load-opbouw.';
  }

  function decoratePrice(chart){
    if(chart.dataset.axesV110==='1')return;
    const vals=priceValues(chart);
    const pos=Math.max(0.01,...vals.filter(v=>v>=0));
    const neg=Math.min(0,...vals.filter(v=>v<0));
    const labels=[fmtPrice(pos),fmtPrice(pos/2),'€ 0,00'];
    const positions=[3,40,78];
    if(neg<0){labels.push(fmtPrice(neg));positions.push(98);}
    const axis=makeAxis('price',labels,positions);
    wrapChart(chart,'price',axis);
    chart.dataset.axesV110='1';
    const note=chart.closest('.ps-section')?.querySelector('.ps-chart-note');
    if(note)note.textContent='Prijs per kwartier in €/kWh. De horizontale 0-lijn scheidt positieve van negatieve prijzen; groen onder nul betekent een negatieve prijs. Geplande acties gebruiken dezelfde 96 kwartierslots.';
  }

  function scan(){
    root.querySelectorAll('.ps-balance-chart').forEach(decorateBalance);
    root.querySelectorAll('.ps-price-chart').forEach(decoratePrice);
  }
  scan();
  new MutationObserver(scan).observe(root,{childList:true,subtree:true});
})();
